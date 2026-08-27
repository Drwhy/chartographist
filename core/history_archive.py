"""Format portable et défensif des archives de présentation."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

from core.presentation import PRESENTATION_SCHEMA_VERSION, snapshot_delta


ARCHIVE_FORMAT = "chartographist-archive"
ARCHIVE_VERSION = 1
MANIFEST_NAME = "manifest.json"

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_MEMBERS = 10_000
MAX_REVISIONS = 100_000
MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_CELLS = 262_144

_KEYFRAME_PATTERN = re.compile(r"keyframes/[0-9]{12}\.json\Z")
_SEGMENT_PATTERN = re.compile(
    r"segments/[0-9]{12}-[0-9]{12}\.ndjson\Z"
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class ArchiveFormatError(ValueError):
    """Erreur structurée d'une archive portable invalide."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _DuplicateJsonKey(ValueError):
    pass


class HistoryArchiveRecorder:
    """Construit une archive par segments avec une mémoire de travail bornée."""

    def __init__(self, path, *, keyframe_interval=60):
        interval = _positive_integer(keyframe_interval)
        if interval is None or interval > MAX_REVISIONS:
            raise ArchiveFormatError("keyframe_interval")
        self.destination = Path(path)
        self.keyframe_interval = interval
        self._temporary = tempfile.TemporaryDirectory(
            prefix=f".{self.destination.name}.recording-",
            dir=self.destination.parent,
        )
        self._root = Path(self._temporary.name)
        (self._root / "keyframes").mkdir()
        (self._root / "segments").mkdir()
        self._members = {}
        self._segment = bytearray()
        self._segment_start = None
        self._first_revision = None
        self._last_revision = None
        self._previous = None
        self._world = None
        self._closed = False
        self._result = None

    def __call__(self, snapshot):
        self.record(snapshot)

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        if error_type is None or issubclass(error_type, KeyboardInterrupt):
            self.finalize()
        else:
            self.abort()
        return False

    def record(self, snapshot):
        """Ajoute un snapshot public sans conserver de référence de l'appelant."""
        if self._closed:
            raise ArchiveFormatError("recorder_closed")
        current = deepcopy(snapshot)
        self._validate_snapshot(current)
        revision = current["revision"]
        if self._last_revision is not None and revision != self._last_revision + 1:
            raise ArchiveFormatError("revision_sequence")

        if self._first_revision is None:
            self._first_revision = revision
            self._world = deepcopy(current["world"])
            self._write_keyframe(current)
            self._segment_start = revision
        elif current["world"] != self._world:
            raise ArchiveFormatError("world_changed")
        elif (revision - self._first_revision) % self.keyframe_interval == 0:
            self._flush_segment(self._last_revision)
            self._write_keyframe(current)
            self._segment_start = revision
        else:
            delta = snapshot_delta(
                self._previous,
                current,
                max_changes=max(1, len(current["cells"])),
            )
            payload = _canonical_json(delta)
            if delta["resync"] or len(payload) > MAX_LINE_BYTES:
                self._flush_segment(self._last_revision)
                self._write_keyframe(current)
                self._segment_start = revision
            elif len(self._segment) + len(payload) + 1 > MAX_MEMBER_BYTES:
                self._flush_segment(self._last_revision)
                self._write_keyframe(current)
                self._segment_start = revision
            else:
                self._segment.extend(payload)
                self._segment.append(10)

        self._previous = current
        self._last_revision = revision

    def finalize(self):
        """Ferme les segments, écrit atomiquement l'archive et nettoie le staging."""
        if self._result is not None:
            return deepcopy(self._result)
        if self._closed:
            raise ArchiveFormatError("recorder_closed")
        if self._first_revision is None:
            self.abort()
            raise ArchiveFormatError("empty_archive")
        self._flush_segment(self._last_revision)
        manifest = {
            "format": ARCHIVE_FORMAT,
            "version": ARCHIVE_VERSION,
            "presentation_schema_version": PRESENTATION_SCHEMA_VERSION,
            "world": deepcopy(self._world),
            "revisions": {
                "first": self._first_revision,
                "last": self._last_revision,
                "keyframe_interval": self.keyframe_interval,
            },
            "capabilities": ["snapshots", "deltas"],
        }
        try:
            self._result = _write_archive_from_paths(
                self.destination,
                manifest,
                self._members,
            )
        finally:
            self._closed = True
            self._temporary.cleanup()
        return deepcopy(self._result)

    def abort(self):
        """Abandonne un enregistrement sans créer l'archive finale."""
        if not self._closed:
            self._closed = True
            self._temporary.cleanup()

    def _validate_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            raise ArchiveFormatError("snapshot_invalid")
        if snapshot.get("schema_version") != PRESENTATION_SCHEMA_VERSION:
            raise ArchiveFormatError("snapshot_invalid")
        revision = _positive_integer(snapshot.get("revision"))
        world = snapshot.get("world")
        cells = snapshot.get("cells")
        if revision is None or not isinstance(world, dict) or not isinstance(cells, list):
            raise ArchiveFormatError("snapshot_invalid")
        width = _positive_integer(world.get("width"))
        height = _positive_integer(world.get("height"))
        if width is None or height is None or width * height > MAX_CELLS:
            raise ArchiveFormatError("snapshot_invalid")
        if len(cells) != width * height:
            raise ArchiveFormatError("snapshot_invalid")
        if not isinstance(world.get("name"), str) or not isinstance(
            world.get("seed"), (str, int)
        ) or isinstance(world.get("seed"), bool):
            raise ArchiveFormatError("snapshot_invalid")
        try:
            _canonical_json(snapshot)
        except ArchiveFormatError as error:
            raise ArchiveFormatError("snapshot_invalid") from error

    def _write_keyframe(self, snapshot):
        name = f"keyframes/{snapshot['revision']:012d}.json"
        payload = _canonical_json(snapshot)
        _validate_member_payload(name, payload)
        self._write_staged(name, payload)

    def _flush_segment(self, end_revision):
        if not self._segment:
            return
        name = (
            f"segments/{self._segment_start:012d}-"
            f"{int(end_revision):012d}.ndjson"
        )
        payload = bytes(self._segment)
        _validate_member_payload(name, payload)
        self._write_staged(name, payload)
        self._segment.clear()

    def _write_staged(self, name, payload):
        path = self._root.joinpath(*PurePosixPath(name).parts)
        path.write_bytes(payload)
        self._members[name] = path


def write_archive(path, manifest, members):
    """Écrit atomiquement une archive canonique et retourne son manifeste."""
    destination = Path(path)
    normalized_members = _normalize_members(members)
    if len(normalized_members) + 1 > MAX_MEMBERS:
        raise ArchiveFormatError("member_limit")
    normalized_manifest = _prepare_manifest(manifest, normalized_members)
    manifest_payload = _canonical_json(normalized_manifest)
    _validate_member_payload(MANIFEST_NAME, manifest_payload)

    total_size = len(manifest_payload) + sum(
        len(payload) for payload in normalized_members.values()
    )
    if total_size > MAX_EXPANDED_BYTES:
        raise ArchiveFormatError("expanded_too_large")

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=False,
        ) as archive:
            _write_member(archive, MANIFEST_NAME, manifest_payload)
            for name, payload in normalized_members.items():
                _write_member(archive, name, payload)
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        if temporary_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ArchiveFormatError("archive_too_large")
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return deepcopy(normalized_manifest)


def _write_archive_from_paths(path, manifest, members):
    """Écrit une archive depuis des membres de staging, un fichier à la fois."""
    destination = Path(path)
    if not isinstance(members, dict) or not members:
        raise ArchiveFormatError("member_mismatch")
    if len(members) + 1 > MAX_MEMBERS:
        raise ArchiveFormatError("member_limit")
    sources = {}
    descriptors = []
    expanded_size = 0
    for name in sorted(members):
        _validate_member_name(name, allow_manifest=False)
        source = Path(members[name])
        if source.is_symlink() or not source.is_file():
            raise ArchiveFormatError("invalid_member")
        size = source.stat().st_size
        if size > MAX_MEMBER_BYTES:
            raise ArchiveFormatError("member_too_large")
        payload = source.read_bytes()
        _validate_member_payload(name, payload)
        expanded_size += size
        descriptors.append({
            "name": name,
            "size": size,
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
        sources[name] = source

    normalized_manifest = deepcopy(manifest)
    capabilities = normalized_manifest.get("capabilities")
    if isinstance(capabilities, list) and all(
        isinstance(value, str) for value in capabilities
    ):
        normalized_manifest["capabilities"] = sorted(capabilities)
    normalized_manifest["members"] = descriptors
    _validate_manifest(normalized_manifest)
    manifest_payload = _canonical_json(normalized_manifest)
    expanded_size += len(manifest_payload)
    if expanded_size > MAX_EXPANDED_BYTES:
        raise ArchiveFormatError("expanded_too_large")

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=False,
        ) as archive:
            _write_member(archive, MANIFEST_NAME, manifest_payload)
            for name, source in sources.items():
                _write_member_from_path(archive, name, source)
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        if temporary_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ArchiveFormatError("archive_too_large")
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return deepcopy(normalized_manifest)


def load_archive_manifest(path):
    """Valide intégralement une archive puis retourne son manifeste défensif."""
    source = Path(path)
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ArchiveFormatError("archive_too_large")
    try:
        with zipfile.ZipFile(source, mode="r") as archive:
            infos = archive.infolist()
            _validate_infos(infos)
            manifest_payload = archive.read(MANIFEST_NAME)
            manifest = _decode_json(
                manifest_payload,
                code="manifest_invalid_json",
                duplicate_code="manifest_duplicate_key",
            )
            _validate_manifest(manifest)
            _validate_manifest_members(archive, infos, manifest)
    except ArchiveFormatError:
        raise
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise ArchiveFormatError("invalid_archive") from error
    return deepcopy(manifest)


def _normalize_members(members):
    if not isinstance(members, dict) or not members:
        raise ArchiveFormatError("member_mismatch")
    normalized = {}
    for name in sorted(members):
        _validate_member_name(name, allow_manifest=False)
        payload = members[name]
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise ArchiveFormatError("invalid_member")
        value = bytes(payload)
        _validate_member_payload(name, value)
        normalized[name] = value
    return normalized


def _prepare_manifest(manifest, members):
    if not isinstance(manifest, dict):
        raise ArchiveFormatError("manifest_invalid")
    result = deepcopy(manifest)
    capabilities = result.get("capabilities")
    if isinstance(capabilities, list) and all(
        isinstance(value, str) for value in capabilities
    ):
        result["capabilities"] = sorted(capabilities)
    result["members"] = [
        {
            "name": name,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for name, payload in members.items()
    ]
    _validate_manifest(result)
    return result


def _validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ArchiveFormatError("manifest_invalid")
    if manifest.get("format") != ARCHIVE_FORMAT:
        raise ArchiveFormatError("manifest_invalid")
    version = manifest.get("version")
    if version != ARCHIVE_VERSION:
        raise ArchiveFormatError("unsupported_version")
    schema_version = manifest.get("presentation_schema_version")
    if schema_version != PRESENTATION_SCHEMA_VERSION:
        raise ArchiveFormatError("manifest_invalid")

    world = manifest.get("world")
    if not isinstance(world, dict) or not isinstance(world.get("name"), str):
        raise ArchiveFormatError("manifest_invalid")
    width = _positive_integer(world.get("width"))
    height = _positive_integer(world.get("height"))
    if width is None or height is None or width * height > MAX_CELLS:
        raise ArchiveFormatError("manifest_invalid")
    if not isinstance(world.get("seed"), (str, int)) or isinstance(
        world.get("seed"), bool
    ):
        raise ArchiveFormatError("manifest_invalid")

    revisions = manifest.get("revisions")
    if not isinstance(revisions, dict):
        raise ArchiveFormatError("manifest_invalid")
    first = _positive_integer(revisions.get("first"))
    last = _positive_integer(revisions.get("last"))
    interval = _positive_integer(revisions.get("keyframe_interval"))
    if first is None or last is None or interval is None or last < first:
        raise ArchiveFormatError("manifest_invalid")
    if last - first + 1 > MAX_REVISIONS:
        raise ArchiveFormatError("revision_limit")

    capabilities = manifest.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(value, str) or not value for value in capabilities)
        or len(set(capabilities)) != len(capabilities)
    ):
        raise ArchiveFormatError("manifest_invalid")

    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise ArchiveFormatError("member_mismatch")
    names = []
    for descriptor in members:
        if not isinstance(descriptor, dict) or set(descriptor) != {
            "name", "size", "sha256"
        }:
            raise ArchiveFormatError("member_mismatch")
        name = descriptor["name"]
        _validate_member_name(name, allow_manifest=False)
        size = descriptor["size"]
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or size > MAX_MEMBER_BYTES
        ):
            raise ArchiveFormatError("member_mismatch")
        if not isinstance(descriptor["sha256"], str) or not _SHA256_PATTERN.fullmatch(
            descriptor["sha256"]
        ):
            raise ArchiveFormatError("member_mismatch")
        names.append(name)
    if names != sorted(names) or len(names) != len(set(names)):
        raise ArchiveFormatError("member_mismatch")


def _validate_infos(infos):
    if len(infos) > MAX_MEMBERS:
        raise ArchiveFormatError("member_limit")
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ArchiveFormatError("duplicate_member")
    for info in infos:
        _validate_member_name(info.filename, allow_manifest=True)
        mode = info.external_attr >> 16
        if info.is_dir() or stat.S_ISLNK(mode) or info.flag_bits & 1:
            raise ArchiveFormatError("unsafe_member")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ArchiveFormatError("member_too_large")
        if info.file_size and info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
            raise ArchiveFormatError("compression_ratio")
    if MANIFEST_NAME not in names:
        raise ArchiveFormatError("manifest_missing")
    if sum(info.file_size for info in infos) > MAX_EXPANDED_BYTES:
        raise ArchiveFormatError("expanded_too_large")


def _validate_manifest_members(archive, infos, manifest):
    physical = {
        info.filename: info for info in infos if info.filename != MANIFEST_NAME
    }
    descriptors = {entry["name"]: entry for entry in manifest["members"]}
    if set(physical) != set(descriptors):
        raise ArchiveFormatError("member_mismatch")
    for name in sorted(physical):
        info = physical[name]
        descriptor = descriptors[name]
        if descriptor["size"] != info.file_size:
            raise ArchiveFormatError("member_mismatch")
        digest = hashlib.sha256()
        payload_parts = []
        with archive.open(info, mode="r") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                payload_parts.append(chunk)
        if digest.hexdigest() != descriptor["sha256"]:
            raise ArchiveFormatError("checksum_mismatch")
        _validate_member_payload(name, b"".join(payload_parts))


def _validate_member_name(name, *, allow_manifest):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ArchiveFormatError("unsafe_member")
    path = PurePosixPath(name)
    if path.is_absolute() or name != path.as_posix() or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ArchiveFormatError("unsafe_member")
    if ":" in path.parts[0]:
        raise ArchiveFormatError("unsafe_member")
    if allow_manifest and name == MANIFEST_NAME:
        return
    if not (_KEYFRAME_PATTERN.fullmatch(name) or _SEGMENT_PATTERN.fullmatch(name)):
        raise ArchiveFormatError("invalid_member")


def _validate_member_payload(name, payload):
    if len(payload) > MAX_MEMBER_BYTES:
        raise ArchiveFormatError("member_too_large")
    if name == MANIFEST_NAME:
        return
    if _KEYFRAME_PATTERN.fullmatch(name):
        value = _decode_json(
            payload,
            code="member_invalid_json",
            duplicate_code="member_duplicate_key",
        )
        if not isinstance(value, dict):
            raise ArchiveFormatError("member_invalid_json")
        return
    if not payload:
        raise ArchiveFormatError("member_invalid_json")
    for line in payload.splitlines():
        if not line or len(line) > MAX_LINE_BYTES:
            raise ArchiveFormatError("member_invalid_json")
        value = _decode_json(
            line,
            code="member_invalid_json",
            duplicate_code="member_duplicate_key",
        )
        if not isinstance(value, dict):
            raise ArchiveFormatError("member_invalid_json")


def _decode_json(payload, *, code, duplicate_code):
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except _DuplicateJsonKey as error:
        raise ArchiveFormatError(duplicate_code) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveFormatError(code) from error


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _canonical_json(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ArchiveFormatError("manifest_invalid") from error


def _write_member(archive, name, payload):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100600 << 16
    archive.writestr(info, payload, compresslevel=6)


def _write_member_from_path(archive, name, source):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100600 << 16
    with source.open("rb") as input_stream, archive.open(
        info,
        mode="w",
        force_zip64=False,
    ) as output_stream:
        while True:
            chunk = input_stream.read(1024 * 1024)
            if not chunk:
                break
            output_stream.write(chunk)


def _positive_integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value
