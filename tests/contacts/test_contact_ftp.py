import unittest
import pytest

from aiohttp import web
from app.contacts import contact_ftp
# from app.service import app_svc
from app.service.app_svc import AppService
from app.utility.base_world import BaseWorld


class TestFtp(unittest.TestCase):
    def setUp(self):
        # create BaseWorld for FTP server
        BaseWorld.apply_config(name='main', config={'app.contact.ftp': '127.0.0.1',
                                                    'app.contact.ftp.dir': '/tmp/caldera',
                                                    'app.contact.ftp.port_in': '2222',
                                                    'app.contact.ftp.port_out': '2224',
                                                    'app.knowledge_svc.module': 'app.utility.base_knowledge_svc',
                                                    'crypt_salt': 'REPLACE_WITH_RANDOM_VALUE',
                                                    'encryption_key': 'ADMIN123',
                                                    'exfil_dir': '/ tmp / caldera',
                                                    'host': '0.0.0.0',
                                                    'plugins': ['sandcat', 'stockpile'],
                                                    'api_key': 'ADMIN123',
                                                    'users': {
                                                        'blue': {
                                                            'blue': 'admin'},
                                                        'red': {
                                                            'admin': 'admin', 'red': 'admin'}
                                                    }
                                                    })
        BaseWorld.apply_config(name='agents', config={'sleep_max': 5,
                                                      'sleep_min': 5,
                                                      'untrusted_timer': 90,
                                                      'watchdog': 0,
                                                      'implant_name': 'splunkd',
                                                      'bootstrap_abilities': [
                                                          '43b3754c-def4-4699-a673-1d85648fda6a'
                                                      ]})
        beacon_profile = {'architecture': 'amd64',
                          'contact': 'ftp',
                          'exe_name': 'sandcat.exe',
                          'executors': ['cmd', 'psh'],
                          'group': 'red',
                          'host': 'testhost',
                          'location': 'C:\\sandcat.exe',
                          'pid': 1234,
                          'platform': 'windows',
                          'ppid': 123,
                          'privilege': 'User',
                          'username': 'testuser'
                          }
        # Get services
        app_svc = AppService(application=web.Application(client_max_size=5120 ** 2))
        services = app_svc.get_services()
        # paw for fake ag
        self.paw = "1234"
        # Files that an agent would send
        f = open("Alive.txt", "w+")
        f.close()

        f = open("test.txt", "w+")
        for i in range(10):
            f.write("This is line %d\r\n" % (i + 1))
        f.close()
        # Startup FTP server
        contact = contact_ftp.Contact(services)
        contact.start()
        self.server = contact_ftp.FtpServer(services)

    # Test if agent can connect with username and password
    async def test_connect_user(self):
        err = await self.server.connect_user("red", "admin")
        assert err is None

    # Test if agent can connect anonymously
    async def test_connect_anonymous(self):
        err = await self.server.connect_anonymous()
        assert err is None

    # Test that upload file catches Alive.txt files as a beacon
    async def test_becon(self):
        err = await self.server.connect_user("red", "admin")
        if err is None:
            err = await self.server.upload_file("Alive.txt", self.paw)
        assert err is True

    # Test that file can be uploaded to the server
    async def test_upload(self):
        err = await self.server.connect_anonymous()
        if err is None:
            err = await self.server.upload_file("test.txt", self.paw)
        assert err is None

    # Test that file can be downloaded from server
    async def test_download(self):
        err = await self.server.connect_user("blue", "admin")
        if err is None:
            err = await self.server.download_file("test.txt", self.paw)
        assert err is None


if __name__ == '__main__':
    unittest.main()
