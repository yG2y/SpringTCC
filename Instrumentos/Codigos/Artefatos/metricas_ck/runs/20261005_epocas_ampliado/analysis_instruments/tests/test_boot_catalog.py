import unittest
from auditar_catalogos_boot import catalog_versions


class BootCatalogTests(unittest.TestCase):
    def test_docker_plugin_does_not_supply_boot_version(self):
        text='''[versions]
docker-spring-boot = "10.0.0"
spring-boot-plugin = "4.1.1"
[plugins]
docker-spring-boot = {id = "com.bmuschko.docker-spring-boot-application", version.ref = "docker-spring-boot"}
spring-boot = {id = "org.springframework.boot", version.ref = "spring-boot-plugin"}
'''
        result=catalog_versions(text)
        self.assertEqual([r['version'] for r in result],['4.1.1'])
        self.assertEqual(result[0]['coordinate'],'org.springframework.boot')

    def test_library_coordinates_and_rich_version_refs(self):
        text='''[versions]
boot = { strictly = "3.5.0" }
[libraries]
boot-bom = { module = "org.springframework.boot:spring-boot-dependencies", version.ref = "boot" }
boot-inline = "org.springframework.boot:spring-boot:3.5.1"
unrelated = "example:spring-boot-support:12.0.0"
'''
        self.assertEqual({r['version'] for r in catalog_versions(text)},{'3.5.0','3.5.1'})

if __name__=='__main__':unittest.main()
