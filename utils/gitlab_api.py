import requests
from urllib.parse import quote

def get_sql_content(
        server_address:str = None,
        private_token:str = None,
        file_name: str = None,
        commit_sha: str = None,
        project_id: str = None
):
    """
    repo_name: git仓库的项目名
    file_name: 文件名 若是多级目录 则以项目为根目录的相对路径，如  folder1/folder2/a.txt
    commit_sha： 哈希版本，commit_sha
    """
    file_path_url_encoded = quote(file_name, safe='')
    api_url = f"{server_address}/api/v4/projects/{project_id}/repository/files/{file_path_url_encoded}/raw?ref={commit_sha}"
    headers = {"PRIVATE-TOKEN": private_token}
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"{response.text}")
