import unittest
from catalogos_gradle import supplemental,amend

class CatalogTests(unittest.TestCase):
    def fixture(self,usage='implementation libraries.boot',catalog=None):
        return {'build.gradle':'apply from: rootProject.file("gradle/dependencies.gradle")\ndependencies {\n'+usage+'\n}',
                'gradle/dependencies.gradle':catalog or 'ext.libraries = [boot: [dependencies.create("org.springframework.boot:spring-boot:$bootVersion") { exclude(group:"org.springframework",module:"spring-core") }], unused: "org.springframework:spring-beans:4"]',
                'gradle.properties':'bootVersion=2.4.1'}
    def test_production_version(self):
        e=supplemental(self.fixture())['evidence'];self.assertEqual(len(e),1);self.assertEqual((e[0]['scope'],e[0]['version']),('production','2.4.1'))
    def test_test_scope(self):self.assertEqual(supplemental(self.fixture('testImplementation libraries.boot'))['evidence'][0]['scope'],'test')
    def test_unused_map(self):self.assertEqual(supplemental(self.fixture('implementation "x:y:1"'))['evidence'],[])
    def test_unapplied_map(self):
        f=self.fixture();f['build.gradle']='implementation libraries.boot';self.assertEqual(supplemental(f)['evidence'],[])
    def test_comments(self):self.assertEqual(supplemental(self.fixture('// implementation libraries.boot\n/* compile libraries.boot */'))['evidence'],[])
    def test_exclusions_ignored(self):
        e=supplemental(self.fixture(catalog='ext.libraries=[boot:[dependencies.create("x:y:1"){exclude("org.springframework.boot:spring-boot:3")}]]'))['evidence'];self.assertEqual(e,[])
    def test_nested_commas_and_maps(self):
        e=supplemental(self.fixture(catalog='ext.libraries=[boot:[dependencies.create("org.springframework.boot:spring-boot:3"){exclude(group:"x",module:"y")}, "org.springframework:spring-core:6"], next: []]'))['evidence'];self.assertEqual(len(e),2)
    def test_toml_indirection(self):
        f=self.fixture(catalog='ext.libraries=[boot:[dependencies.create(libs.spring.boot.core.get()) { exclude(group:"x",module:"y") }]]')
        f['gradle/libs.versions.toml']='[versions]\nboot="3.2"\n[libraries]\nspring-boot-core={module="org.springframework.boot:spring-boot",version.ref="boot"}'
        e=supplemental(f)['evidence'];self.assertEqual(e[0]['version'],'3.2')
    def test_subproject(self):
        f=self.fixture('');f['module/build.gradle']='compile libraries.boot';self.assertEqual(supplemental(f)['evidence'][0]['file'],'module/build.gradle')
    def test_ambiguous_definition(self):
        f=self.fixture();f['build.gradle']+='\napply from: "other.gradle"';f['other.gradle']='ext.libraries=[boot:"org.springframework.boot:spring-boot:3"]'
        e=supplemental(f);self.assertEqual(e['evidence'],[]);self.assertEqual(e['unresolved'][0]['reason'],'ambiguous_catalog_definition')
    def test_unresolved_version(self):
        f=self.fixture();del f['gradle.properties'];self.assertEqual(supplemental(f)['evidence'][0]['version'],'$bootVersion')
    def test_no_plugin_as_dependency(self):self.assertEqual(supplemental(self.fixture('classpath libraries.boot'))['evidence'],[])
    def test_source_role_preserved(self):
        original=dict(framework='framework_source',framework_confirmed=False,evidence=[],diagnostics=[],detection='static')
        a=amend(original,supplemental(self.fixture()));self.assertEqual(a['framework'],'framework_source');self.assertFalse(a['boot_present'])
    def test_test_only_not_boot(self):
        original=dict(framework='not_confirmed',framework_confirmed=False,evidence=[],diagnostics=[],detection='static')
        a=amend(original,supplemental(self.fixture('testImplementation libraries.boot')));self.assertEqual(a['framework'],'test_only');self.assertFalse(a['boot_present'])

if __name__=='__main__':unittest.main()
