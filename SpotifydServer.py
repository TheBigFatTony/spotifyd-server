import os
import shutil
import json
import requests
from subprocess import Popen, PIPE

import wget as wget

path_to_file = os.path.dirname(os.path.abspath(__file__))

SPOTIFYD_BIN = '/home/pi/spotifyd'
SPOTIFYD_CACHE_DIR = '/home/pi/.spotifyd_cache'
SPOTIFYD_VERSION = 'spotifyd-linux-armv6-slim'


class UwsgiResponder:
    def __init__(self, env, start_response):
        self.env = env
        self.start_response = start_response

    def return_html(self):
        if self.start_response is not None:
            self.start_response('200 OK', [('Content-Type', 'text/html')])

        index_html = open(F'{path_to_file}/index.html').read()
        return [str.encode(index_html)]

    def return_json(self, content: dict):
        if self.start_response is not None:
            self.start_response('200 OK', [('Content-Type', 'application/json')])

        test = json.dumps(content)
        test = test.encode('utf-8')
        return [test]

    def redirect(self, to: str = ''):
        REDIRECT_TO = self.env['HTTP_HOST']
        if self.start_response:
            self.start_response('302 Found', [('Location', F'http://{REDIRECT_TO}/{to}')])
        return []

    @property
    def URL(self):
        return self.env['REQUEST_URI']


class GitHubReleaseDownloader:
    def __init__(self, repo: str):
        self.repo = repo
        response = requests.get(F'https://api.github.com/repos/{self.repo}/releases/latest')
        self.response = response.json()
        self._orig_assets = self.response['assets']
        self.assets = self._orig_assets

    @property
    def version(self):
        return self.response['tag_name']

    def filter_assets(self, query: str, asset_key='name', exact=True):
        if exact:
            assets = [asset for asset in self._orig_assets if query == asset[asset_key]]
        else:
            assets = [asset for asset in self._orig_assets if query in asset[asset_key]]
        if not len(assets) == 1:
            print(F'Found {len(assets)} matching assets in {self.repo}! (field={asset_key}, query={query})')
        self.assets = assets

    def download_asset(self, out: str):
        assert os.path.isdir(out)
        assert len(self.assets) == 1, \
            F'Multiple {len(self.assets)} assets found - please filter assets first! (GitHubReleaseDownloader.filter_assets)'
        asset = self.assets[0]
        url = asset['browser_download_url']
        assert url.endswith('.tar.gz'), F'GitHubReleaseDownloader only deals with .tar.gz-files! {url}'
        wget.download(url=url, out=out)
        basename = url.rsplit('/', maxsplit=1)[1]

        assert os.path.isfile(os.path.join(out, basename))


class Execute:
    @classmethod
    def execute(cls, cmd: [str], expected_returncode: int = 0, timeout=None, cwd=None) -> (str, str):
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=cwd)
        p.wait(timeout=timeout)

        stdout, stderr = p.communicate()
        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

        if expected_returncode is not None:
            assert p.returncode == expected_returncode, \
                F'Command failed: "{" ".join(cmd)}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"'

        return stdout, stderr

    @classmethod
    def execute_to_dict(cls, cmd: [str], action_name: str, expected_returncode: int = 0, timeout=None, cwd=None) -> dict:
        try:
            stdout, stderr = cls.execute(cmd, expected_returncode, timeout, cwd)
            return dict(action=action_name, success=True, stdout=stdout, stderr=stderr)
        except Exception as e:
            return dict(action=action_name, success=False, message=str(e))


class Actions:
    @staticmethod
    def restart():
        response = Execute.execute_to_dict(
            cmd=['systemctl', '--user', 'stop', 'spotifyd.service'],
            action_name='restart'
        )

        if not response['success']:
            return response

        if os.path.isdir(SPOTIFYD_CACHE_DIR):
            shutil.rmtree(SPOTIFYD_CACHE_DIR)
        os.makedirs(SPOTIFYD_CACHE_DIR, exist_ok=True)

        return Execute.execute_to_dict(
            cmd=['systemctl', '--user', 'start', 'spotifyd.service'],
            action_name='restart'
        )

    @staticmethod
    def update():
        try:
            tmp_dir = F'{SPOTIFYD_CACHE_DIR}/.update'
            asset_name = 'spotifyd-linux-armv6-slim.tar.gz'

            os.makedirs(tmp_dir, exist_ok=True)
            g = GitHubReleaseDownloader('Spotifyd/spotifyd')
            g.filter_assets(asset_key='name', query=asset_name)
            g.download_asset(out=tmp_dir)

            Execute.execute(cmd=['tar', '-xzf', F'{tmp_dir}/{asset_name}', '--directory', tmp_dir])

            assert 'spotifyd' in os.listdir(tmp_dir)

            os.rename(F'{tmp_dir}/spotifyd', SPOTIFYD_BIN)

            response = Actions.restart()
            assert response['success'] == True, F'Failed to restart: {response}'

            return dict(action='update', success=True, message=F'Updated to version {g.version}')
        except Exception as e:
            return dict(action='update', success=False, message=str(e))

    @staticmethod
    def update_self():
        response = Execute.execute_to_dict(['git', 'pull'], action_name='update-self', cwd=path_to_file)

        if not response['success']:
            return response

        return Execute.execute_to_dict(
            cmd=['systemctl', '--user', 'start', 'spotifyd_server.service'],
            action_name='restart'
        )

    @staticmethod
    def shutdown():
        return Execute.execute_to_dict(
            cmd=['sudo', 'systemctl', 'poweroff'],
            action_name='shutdown', timeout=5
        )

    @staticmethod
    def reboot():
        return Execute.execute_to_dict(
            cmd=['sudo', 'systemctl', 'reboot'],
            action_name='reboot', timeout=5
        )

    @staticmethod
    def act(action: str) -> dict:
        assert action != 'act', F'This is not a valid action: {action}'
        assert hasattr(Actions, action), F'This is not a valid action: {action}'
        action = getattr(Actions, action)
        return action()


def application(env, start_response):
    responder = UwsgiResponder(env, start_response)
    URL = responder.URL

    if URL == '/':
        return responder.return_html()

    elif URL in ['/restart', '/update', '/update_self', '/shutdown', '/reboot']:
        action = URL[1:]
        response = Actions.act(action)
        return responder.return_json(response)

    else:
        return responder.redirect()
