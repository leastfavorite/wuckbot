from .typed_dict import TypedDict, TypedDictMeta
from .serializer import Registrar

from typing import Union
import json
from pathlib import Path
from datetime import datetime, UTC
import hashlib

# singleton
class JsonFileMeta(TypedDictMeta):
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                JsonFileMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def _json_file_save(self, filename, backups_folder, registrar):

    def _make_backup(backup_count: int = 10):
        if backup_count <= 0:
            return

        current_backup = filename
        stem = current_backup.stem
        suffix = current_backup.suffix
        dt = datetime.now(UTC).strftime("%y-%m-%d-%H%M%S")
        backup_stem = f"{stem}-{dt}{suffix}"

        # check if backups exist
        backups: list[Path] = list(backups_folder.glob(f"{stem}-*{suffix}"))

        if backups:
            # get most recent backup
            backups.sort(key=lambda x: x.stat().st_ctime_ns, reverse=True)
            last_backup = backups[0]

            # if the files are the same size
            last_backup_size = last_backup.stat().st_size
            current_size = current_backup.stat().st_size

            if last_backup_size == current_size:

                # with matching hashes
                with current_backup.open("rb") as fp:
                    current_hash = hashlib.file_digest(fp, "sha256")
                with last_backup.open("rb") as fp:
                    last_hash = hashlib.file_digest(fp, "sha256")

                if current_hash.digest() == last_hash.digest():
                    # the file wasn't updated
                    return

        # make a new backup
        current_backup.rename(backups_folder / backup_stem)

        # keep only the {backup_count} most recent backups
        for old_backup in backups[backup_count-1:]:
            old_backup.unlink()


    async def save(backup_count: int = 10):
        serialized = await registrar.serialize(self, type(self))
        if not serialized:
            raise RuntimeError(f"Could not save {type(self).__qualname__}")

        _make_backup(backup_count)

        with filename.open("w") as fp:
            json.dump(serialized, fp, indent=2)

    return save


class JsonFile(TypedDict, metaclass=JsonFileMeta):

    @classmethod
    async def create(cls, *args, **kwargs):
        raise RuntimeError("Use load() instead")

    @classmethod
    async def load(cls,
                   filename: Union[str, Path],
                   backups_folder: Union[str, Path],
                   registrar: Registrar):

        if not isinstance(backups_folder, Path):
            backups_folder = Path(backups_folder)
        if not isinstance(filename, Path):
            filename = Path(filename)

        if filename.exists() and not filename.is_file():
            raise FileExistsError(f"{filename} exists and is not a file.")

        if backups_folder.exists() and not backups_folder.is_dir():
            raise FileExistsError(f"{filename} exists and is not a directory.")

        data_raw = {}
        if filename.exists() and filename.stat().st_size > 0:
            with open(filename, "r") as fp:
                data_raw = json.load(fp)

        instance = await registrar.deserialize(data_raw, cls)
        if not instance:
            raise RuntimeError(
                f"{cls.__qualname__} couldn't be resolved from {filename}.")

        setattr(instance, 'save',
                _json_file_save(instance, filename, backups_folder, registrar))
        backups_folder.mkdir(parents=True, exist_ok=True)

        return instance

    # define here so autocomplete can find it
    async def save(self, backups_count: int = 10):
        raise RuntimeError("This should be overwritten on load.")

# import disnake
#
# class Secrets(JsonFile):
#     test_guilds: list[disnake.Guild]
#     bot_token: str
#     admin: disnake.User
#     soundcloud_oauth: str
#
# class LinkedUser(TypedDict):
#     discord: disnake.User
#     soundcloud: soundcloud.User
#
# class State(JsonFile):
#     wips: list[Wip]
#     soundclouds: list[LinkedUser]

# TODO!
# - implement serializers for soundcloud stuff
# - get main back to running
