import psycopg2
from datetime import datetime
from util.getconfig import GetYamlConfig

pg_config = GetYamlConfig().get_config('Tool')['Postgres']
__all__ = ['PostgresClient']

class PostgresClient(object):
    def __init__(self, table_catalog):
        self.host = pg_config.get('host')
        self.port = pg_config.get('port')
        self.user = pg_config.get(table_catalog)['user']
        self.__password = pg_config.get(table_catalog)['password']
        self.database = pg_config.get(table_catalog)['database']
        self._conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.__password,
            database=self.database
        )

    def select_bk_table(
            self,
            table_scheme: str='public',
            table_catalog: str='dbtest',
            table_name: str='t_stu'
        ) -> str:
        try:
            today_format = datetime.now().strftime('%m%d')
            self._cursor = self._conn.cursor()
            sql_content = f"""select table_name from information_schema."tables" t where
table_schema = '{table_scheme}'
and table_catalog = '{table_catalog}'
and table_name like 'bk_{today_format}_{table_name}_%';"""
            self._cursor.execute(sql_content)
            # 查询当前是否存在备份表，返回备份表名
            execute_result = self._cursor.fetchall()
            if not execute_result:
                bk_table_name = f"bk_{today_format}_1_{table_name}"
            else:
                last_bk_table_name = execute_result[-1][0]
                # current_bk_index = int(last_bk_table_name.split('_')[-1]) + 1
                current_bk_index = int(last_bk_table_name.split('_')[2]) + 1
                bk_table_name = f"bk_{today_format}_{current_bk_index}_{table_name}"
            return bk_table_name

        except Exception as err:
            return_data = {
                'status': False,
                'msg': '查询 pg 数据库备份表信息失败，请检查',
                'data': f'异常原因{err.__str__()}'
            }
            return return_data
        finally:
            self._cursor.close()
            self._conn.close()
