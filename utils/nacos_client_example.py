from nacos_client import NacosClient
import traceback
import re


# 通过文本方式修改的配置
def update_config_property(config_text, key, value):
    # 将原始配置文本按行拆分
    lines = config_text.split('\n')
    # 使用正则表达式匹配配置项，并替换对应的值
    for i, line in enumerate(lines):
        match = re.match(r'^\s*{} = (.*)$'.format(re.escape(key)), line)
        if match:
            lines[i] = '{} = {}'.format(key, value)
            break  # 找到匹配项后就退出循环
    # 如果没有找到对应的配置项，则添加新的配置项
    else:
        lines.append('{} = {}'.format(key, value))
    # 将更新后的配置文本重新组合成字符串并返回
    return '\n'.join(lines)


def format_data_from_jira(nacos_info):
    data = {}
    for i in nacos_info.split('\r\n'):
        columns = i.split('@@')
        data_id = columns[2]
        item = {
            "action": columns[0],
            "user": columns[1],
            "key": columns[3],
            "value": columns[4],
        }
        if data_id in data:
            data[data_id].append(item)
        else:
            data[data_id] = []
    return data


def example():
    # 指定使用哪个namespace
    namespace = "29d881a1-70bd-4fb2-90b9-03ae5989e1d4"
    group = "DEFAULT_GROUP"
    # 将nacos配置按照dataId分组
    nacos_info = 'update@@map@@map-test.propertles@@key1@@value1\r\nupdate@@pitt@@map-test.propertles@@key2@@value2'
    nacos_keys = format_data_from_jira(nacos_info)
    # nacos_keys = {
    #     "map-test.propertles": [
    #         {"action": "update", "key": "key1", "value": "11"},
    #         {"action": "update", "key": "key2", "value": "22"},
    #         {"action": "update", "key": "key3", "value": "33"},
    #         {"action": "add", "key": "key4", "value": "44"},
    #     ],
    # }
    # 创建客户端
    nacos_client = NacosClient()

    for data_id, keys in nacos_keys.items():
        # 从nacos获取配置
        confit_text = nacos_client.get_config(namespace=namespace, group=group, data_id=data_id)
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

        # 修改配置并改回nacos
        new_config = nacos_client.update_config(config_dict, keys)
        content = nacos_client.convert_dict_to_text(new_config)
        message = nacos_client.post_config(namespace=namespace, group=group, data_id=data_id, content=content)
        print(message)


def test_read_all_config():
    namespace = "aa06-4436-aaf0-2878c72f2dc6-36994748"
    # namespace = "36994748-aa06-4436-aaf0-2878c72f2dc6"
    group = "DEFAULT_GROUP"
    # 以data_id 为操作批次
    data_ids = [
        "shared-redis-config",
        "shared-db-config",
        "shared-mq-config",
        "shared-config",
        "game-center-mqtt-service.properties",
        "game-center-service.properties",
        "game-server-service.properties",
        "gateway-service.properties",
        "gci-service.properties",
        "job-admin.properties",
        "job-executor.properties",
        "web-service.properties",
        "office.properties",
        "ocr-service.properties",
        "report-service.properties",
        "pachinko-web-service.properties",
        "pachinko-game-server-service.properties",
        "machine-manage",
        "manage-db-config"
    ]
    nacos_client = NacosClient()
    for data_id in data_ids:
        try:
            confit_text = nacos_client.get_config(namespace=namespace, group=group, data_id=data_id)
            config_dict = nacos_client.convert_text_to_dict(confit_text)
            for key, data in config_dict.items():
                if not data["value"]:
                    print(data_id, key)
        except Exception as error:
            message = traceback.format_exc()
            print(message)


if __name__ == '__main__':
    example()
    # test_read_all_config()

