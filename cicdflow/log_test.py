import logging
c_logger = logging.getLogger('console_logger')
d_logger = logging.getLogger('default_logger')

def log_test():
    print('here is log_test')
    c_logger.debug('debug log for console_logger...')
    c_logger.info('info log for console_logger...')

    d_logger.info('info log for default_logger...')
    d_logger.error('error log for default_logger...')
