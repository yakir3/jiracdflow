import requests
from urllib.parse import quote


# git仓库的项目名与项目ID的映射关系
git_project_name_id_map = {
    "is03-cashsite": 320,
    "bw01-cashsite": 321,
    "ipachinko-merchant": 225,
    "isagent-report": 318,
    "isagent-merchant": 317,
    "isagent-admin": 316,
    "sql_islot_islot-uat_iltm01": 154,
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
