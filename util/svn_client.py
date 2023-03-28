import svn.remote
import svn.local
import shutil

try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig

svn_config = GetYamlConfig().get_config('Tool')['SVN']
__all__ = ['SvnClient']

class SvnClient(object):
    """SVN"""
    def __init__(self, svn_path):
        self._url = svn_config['url']
        self._username = svn_config['username']
        self._password = svn_config['password']
        self._svn_path = self._url + svn_path
        self.remote = svn.remote.RemoteClient(self._svn_path, username=self._username, password=self._password)

    def _checkout(self, path=None, revision=None):
        self.remote.checkout(path=path, revision=revision)

    def get_file_content(self, revision=None, filename=None):
        # svn 临时目录，会进行目录删除，不能随意修改
        tmp_path = '/tmp/svn_tmp_path'
        try:
            self._checkout(path=tmp_path, revision=revision)
            with open(f'{tmp_path}/{filename}') as f:
                file_content = f.read()
                # 清理 svn 临时目录
                shutil.rmtree(f'{tmp_path}')
                return file_content
        except Exception as err:
            print(err.__str__())
            # 清理 svn 临时目录
            shutil.rmtree(f'{tmp_path}')

if __name__ == '__main__':
    pass