import svn.remote
import svn.local
import shutil
import tempfile

__all__ = ['SvnClient']

class SvnClient(object):
    """SVN"""
    def __init__(
            self,
            host: str = None,
            username: str = None,
            password: str = None,
            svn_path: str = None
    ):
        self.svn_path = f"svn://{host}{svn_path}"
        self._username = username
        self._password = password
        self.remote = svn.remote.RemoteClient(
            self.svn_path,
            username=self._username,
            password=self._password
        )

    def _checkout(self, path=None, revision=None):
        self.remote.checkout(path=path, revision=revision)

    def get_file_content(self, revision=None, filename=None) -> str:
        try:
            with tempfile.TemporaryDirectory(dir='/tmp') as temp_dir:
                self._checkout(path=temp_dir, revision=revision)
                f = open(f"{temp_dir}/{filename}")
                sql_content = f.read()
                f.close()
            return sql_content
        except Exception as err:
            # shutil.rmtree(temp_dir)
            return f"获取 svn sql 内容时异常，异常原因：{err.__str__()}"

if __name__ == '__main__':
    pass