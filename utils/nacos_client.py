import requests
from collections import OrderedDict
import copy
from utils.getconfig import GetYamlConfig


__all__ = ['NacosClient']


# 获取 JIRA 配置信息
nacos_config = GetYamlConfig().get_config('NACOS')


class NacosClient:
    def __init__(self, server_address=None, username=None, password=None):
        self.server_address = server_address
        self.username = username
        self.password = password
        self.token = self.__login__()

    def __login__(self):
        url = f'{self.server_address}/v1/auth/login'
        post_data = {"username": self.username, "password": self.password}
        response = requests.post(url=url, data=post_data)
        data = response.json()
        token = data.get("accessToken", "None")
        return token

    def get_config(self, namespace=None, group=None, data_id=None):
        url = f"{self.server_address}/v2/cs/config"
        post_data = {
            "namespaceId": namespace,
            "group": group,
            "dataId": data_id,
            "accessToken": self.token
        }
        response = requests.get(url, params=post_data)
        return response.json()

    def post_config(self, namespace=None, group=None, data_id=None, content=None):
        """
            content: type: str,  配置文件文本内容
        """
        url = f"{self.server_address}/v2/cs/config"
        post_data = {
            "namespaceId": namespace,
            "group": group,
            "dataId": data_id,
            "accessToken": self.token,
            "content": content
        }
        response = requests.post(url, data=post_data)
        return response.json()

    @staticmethod
    def convert_text_to_dict(data_text):
        """
            功能：将文本格式的配置文件转换成dict类型
            说明：既可以将配置文件转成纯key-value形式的字典便于操作，后面还原成文本时还能保存其原始的空行和注释信息
                空行和注释保存到其后面第一个key的no_data_line属性中
                （注意：配置文件末尾的多余的多个空行无法保存）
            类似如下:
            return {
                "key1": {"value": "value1", "no_data_line": ""}
                "key2": {"value": "value2", "no_data_line": "\n\n# 注释....\n"}
            }
        """
        data_dict = OrderedDict()
        lines = data_text.split('\n')
        no_data_line = ''
        for line in lines:
            if line.strip():
                if line.startswith('#'):
                    no_data_line += line.strip()
                    no_data_line += "\n"
                else:
                    # 仅拆分一次，避免值中含有 '=' 字符
                    key, value = line.split('=', 1)
                    data_dict[key.strip()] = {"value": value.strip(), "no_data_line": no_data_line}
                    no_data_line = ''
            else:
                no_data_line += '\n'
        return data_dict

    @staticmethod
    def check_all_keys(data_dict, key_list):
        """
            说明：校验所有的后面流程需要操作(add, delete, update)的配置key是否已经存在或不存在
            keys = [
                {"action": "delete", "key": "key1", "value": "value1"},
                {"action": "add", "key": "key2", "value": "value2"},
                {"action": "update", "key": "key3", "value": "value3"}
            ]
            return dict
                若：返回的字典值为空，则所有的key时符合操作要去
                若：返回的字典值不空，则字典的key对应的value则是具体的报错信息
            返回值类似如下：
                {
                    "key1": "key不存在,无法删除",
                    "key2": "key不存在,无法修改",
                    "key3": "key已存在,无法新增",
                }
        """
        error_message_data = {}
        for i in key_list:
            key_name = i["key"]
            if i["action"] == "delete" and key_name not in data_dict:
                error_message_data[key_name] = "key不存在,无法删除"
            if i["action"] == "add" and key_name in data_dict:
                error_message_data[key_name] = "key已存在,无法新增"
            if i["action"] == "update" and key_name not in data_dict:
                error_message_data[key_name] = "key不存在,无法修改"
        return error_message_data

    @staticmethod
    def convert_dict_to_text(data_dict):
        lines_list = []
        for key, key_data in data_dict.items():
            lines_list.append(key_data["no_data_line"])
            item = f"{key} = {key_data['value']}\n"
            lines_list.append(item)
        data_text = ''.join(lines_list)
        return data_text

    @staticmethod
    def update_config(data_dict, key_list):
        new_data_dict = copy.deepcopy(data_dict)
        for i in key_list:
            key_name = i["key"]
            if i["action"] == "delete":
                new_data_dict.pop(key_name)
            if i["action"] == "add":
                new_data_dict[key_name] = {"value": i["value"], "no_data_line": ""}
            if i["action"] == "update":
                new_data_dict[key_name]["value"] = i["value"]
        return new_data_dict


if __name__ == "__main__":
    # 通用配置
    server_address = "https://slnacos.opsre.net"
    username = "map"
    password = 'acclub.io666'
    namespace = "29d881a1-70bd-4fb2-90b9-03ae5989e1d4"
    group = "DEFAULT_GROUP"
    # 以data_id 为操作批次
    data_id = "map-test.propertles"
    # 将nacos配置按照dataId分组
    nacos_keys = {
        "map-test.propertles": [
            {"action": "update", "key": "key1", "value": "11"},
            {"action": "update", "key": "key2", "value": "22"},
            {"action": "update", "key": "key3", "value": "33"},
            {"action": "add", "key": "key4", "value": "44"},
        ],
    }
    # 创建客户端
    nacos_client = NacosClient(server_address=server_address, username=username, password=password)
    for data_id, keys in nacos_keys.items():
        # 从nacos获取配置
        config_data = nacos_client.get_config(namespace=namespace, group=group, data_id=data_id)
        confit_text = config_data["data"]
        # 把从nacos获取到的配置 由文本 转换为 dict类型
        config_dict = nacos_client.convert_text_to_dict(confit_text)
        # 检查要操作的key与对的action是否合规(有该key才可以删除和修改，无该key才可以新增)
        check_keys_message = nacos_client.check_all_keys(config_dict, keys)
        if check_keys_message:
            for key, message in check_keys_message.items():
                print(data_id, key, message)
            raise "配置文件keys校验未通过"
        else:
            print("配置文件keys校验通过")
        # 修改配置并写入nocos
        new_config = nacos_client.update_config(config_dict, keys)
        content = nacos_client.convert_dict_to_text(new_config)
        data = nacos_client.post_config(namespace=namespace, group=group, data_id=data_id, content=content)
        message = data["message"]
        print(f"配置文件修改: {message}")
