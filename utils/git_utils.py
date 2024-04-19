import requests
from urllib.parse import quote


# git仓库的项目名与项目ID的映射关系
git_project_name_id_map = {
    "isagent_isagent-admin": 316,
    "isagent_isagent-merchant": 317,
    "isagent_isagent-report": 318,
    "isagent_ipachinko-merchant": 319,
    "isagent_bw01-cashsite": 321,
    "islot_islot-main": 328,
    "islot_islot-v2": 329
}

def get_sql_content(server_address=None, private_token=None, repo_name=None, file_name=None, commit_sha=None):
    """
    repo_name: git仓库的项目名
    file_name: 文件名 若是多级目录 则以项目为根目录的相对路径，如  folder1/folder2/a.txt
    commit_sha： 哈希版本，commit_sha
    """
    project_id = git_project_name_id_map.get(repo_name)
    file_path_url_encoded = quote(file_name, safe='')

    api_url = f'{server_address}/api/v4/projects/{project_id}/repository/files/{file_path_url_encoded}/raw?ref={commit_sha}'
    headers = {'PRIVATE-TOKEN': private_token}
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"{response.text}")
