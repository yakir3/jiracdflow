import smtplib, socket
from email.mime.text import MIMEText
from email.header import Header
from ntlm_auth.ntlm import Ntlm

from util.getconfig import GetYamlConfig

workstation = socket.gethostname().upper()
email_config = GetYamlConfig().get_config('Tool')['Email']

__all__ = ['EmailClient']

class EmailClient(object):
    def __init__(self):
        self._smtp_server = email_config['smtp_server']
        self._smtp_port = email_config['smtp_port']
        self._sender = email_config['sender']
        self._password = email_config['password']
        self._from = email_config['from']
        self._to = email_config['to']
        self._receivers = email_config['receivers']

    @staticmethod
    def ntlm_authenticate(smtp, domain, username, password):
        code, response = smtp.docmd("AUTH", "NTLM")
        ntlm_context = Ntlm(ntlm_compatibility=2)
        if code != 334:
            raise Exception("Server did not respond as expected to NTLM negotiate message")

        code, response = smtp.docmd(ntlm_context.create_negotiate_message(domain, workstation).decode())
        if code != 334:
            raise Exception("Server did not respond as expected to NTLM challenge message")

        ntlm_context.parse_challenge_message(response)
        code, response = smtp.docmd(ntlm_context.create_authenticate_message(username, password,domain, workstation).decode())
        if code != 235:
            raise Exception(code, response)

    def send_email(self, send_msg: object, email_summary: object) -> dict:
        send_result = {
            'status': True,
            'msg': ''
        }
        try:
            sender = self._sender
            username, domain = sender.split("@")
            password = self._password
            receivers = self._receivers
            send_msg = send_msg

            # message = MIMEText(send_msg, 'html', 'utf-8')
            message = MIMEText(send_msg, 'plain', 'utf-8')
            message['From'] = Header(self._from)
            message['To'] = Header(self._to)
            message['Subject'] = Header(f"升级工单: {email_summary}", 'utf-8')

            smtpobj = smtplib.SMTP(self._smtp_server, self._smtp_port)
            smtpobj.starttls()
            smtpobj.ehlo()
            # NTLM验证
            self.ntlm_authenticate(smtpobj, domain, username, password)
            smtpobj.sendmail(sender, receivers, message.as_string())
            send_result['msg'] = '邮件发送成功.'
        except Exception as err:
            send_result['status'] = False
            send_result['msg'] = err.__str__()
        return send_result