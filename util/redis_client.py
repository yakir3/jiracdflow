import redis
try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig

redis_config = GetYamlConfig().get_config('Tool')['Redis']

class RedisClient(object):
    """Redis"""
    def __init__(self):
        self._conf = redis_config
        self.redis_client = redis.Redis(**self._conf)

if __name__ == '__main__':
    r = RedisClient().redis_client
    print(r.llen('yakir'))
