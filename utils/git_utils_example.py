from git_utils import get_sql_content
from utils.getconfig import GetYamlConfig


git_config = GetYamlConfig().get_config('GIT')
server_address = git_config["server_address"]
private_token = git_config["private_token"]

# sql处理
def do_other_things(sql):
    print("sql 执行成功")


# 使用示例
def example():
    # jira的原始数据类似如下
    data = {
        'sql_info': 'bw01-cashsite@@README.md@@ea56c930b1376e3eeabc501bad5925f0f51ff6e1\r\nis03-cashsite@@README.md@@c9936ee268589a70ca9bf392a41269f7491af3ab',
    }
    # 格式化数据
    sql_list = []
    for i in data["sql_info"].split("\r\n"):
        item = {
            "repo_name": i.split("@@")[0],
            "file_name": i.split("@@")[1],
            "commit_sha": i.split("@@")[2],
        }
        sql_list.append(item)
    # 数据处理
    for sql_item in sql_list:
        try:
            content = get_sql_content(
                server_address=server_address,
                private_token=private_token,
                repo_name=sql_item["repo_name"],
                file_name=sql_item["file_name"],
                commit_sha=sql_item["commit_sha"]
            )
            print(f"repo_name: {sql_item['repo_name']} file_name: {sql_item['file_name']} 获取sql内容正常")
            # 调用其他的逻辑处理SQL
            do_other_things(content)
        except Exception as error:
            print(f"获取sql失败，{error}")


if __name__ == '__main__':
    example()
