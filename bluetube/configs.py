import importlib.resources as pkg_resources
import os

import toml


class Configs(object):
    '''
    Manages bluetube configurations in conf.toml.
    '''
    CONFIG_FILE_NAME = 'configs.toml'

    @staticmethod
    def create_configs(bt_dir):
        path = os.path.join(bt_dir, Configs.CONFIG_FILE_NAME)
        if not os.path.exists(path):
            # probably the script has just been installed
            # create the file from the template
            template = pkg_resources.read_text(__package__,
                                               Configs.CONFIG_FILE_NAME)
            with open(path, 'w') as f:
                f.write(template)
        return path

    def __init__(self, bt_dir):
        self._config_path = Configs.create_configs(bt_dir)
        self._configs = toml.load(self._config_path)

    def get_editor(self) -> str:
        def_ed = os.environ.get('EDITOR')
        if def_ed:
            return def_ed
        return self._configs.get('editor').get('default')

    def set_editor(self, ed: str):
        self._configs['editor']['default'] = ed
        self._dump()

    def get_media_player(self):
        return self._configs.get('media_player').get('default')

    def set_media_player(self, player: str):
        self._configs['media_player']['default'] = player
        self._dump()

    def _dump(self):
        with open(self._config_path, 'w') as f:
            toml.dump(self._configs, f)
