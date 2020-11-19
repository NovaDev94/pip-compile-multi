"""Tests for pip-compile-multi"""

import os
try:
    from unittest import mock
except ImportError:
    import mock

import pytest

from pipcompilemulti.environment import Environment
from pipcompilemulti.dependency import Dependency
from pipcompilemulti.options import OPTIONS
from pipcompilemulti.deduplicate import PackageDeduplicator
from pipcompilemulti.utils import merged_packages, relation_cluster
from pipcompilemulti.features.header import DEFAULT_HEADER


PIN = 'pycodestyle==2.3.1        # via flake8'
CMPT = 'pycodestyle~=2.3.1        # via flake8'


def test_fix_compatible_pin():
    """Test == is replaced with ~= for compatible dependencies"""
    env = Environment('xxx')
    with mock.patch.dict(OPTIONS, {'compatible_patterns': ['pycode*']}):
        result = env.fix_pin(PIN)
    assert result == CMPT


def test_no_fix_incompatible_pin():
    """Test dependency is left unchanged be default"""
    env = Environment('')
    result = env.fix_pin(PIN)
    assert result == PIN


def test_pin_is_ommitted_if_set_to_ignore():
    """Test ignored files won't pass"""
    dedup = PackageDeduplicator()
    dedup.on_discover([{'name': 'a', 'refs': ['b']}, {'name': 'b', 'refs': []}])
    dedup.register_packages_for_env('b', {'pycodestyle': '2.3.1'})
    env = Environment('a', deduplicator=dedup)
    result = env.fix_pin(PIN)
    assert result is None


def test_post_releases_are_kept_by_default():
    """Test postXXX versions are truncated to release"""
    pin = 'pycodestyle==2.3.1.post2231  # via flake8'
    env = Environment('')
    result = env.fix_pin(pin)
    assert result == pin


def test_forbid_post_releases():
    """Test postXXX versions are kept if allow_post=True"""
    pin = 'pycodestyle==2.3.1.post2231  # via flake8'
    with mock.patch.dict(OPTIONS, {'forbid_post': ['env']}):
        env = Environment('env')
        result = env.fix_pin(pin)
    assert result == PIN


@pytest.mark.parametrize('name, refs', [
    ('base.in', set()),
    ('test.in', {'base'}),
    ('local.in', {'test'}),
])
def test_parse_relations(name, refs):
    """Check references are parsed for sample files"""
    env = Environment('')
    result = env.parse_relations(os.path.join('requirements', name))['refs']
    assert result == refs


def test_split_header():
    """Check that default header is parsed from autogenerated base.txt"""
    with open(os.path.join('requirements', 'base.txt')) as fp:
        header, _ = Environment.split_header(fp)
    expected = [
        line + '\n'
        for line in DEFAULT_HEADER.splitlines()
    ]
    assert header[1:] == expected


def test_concatenation():
    """Check lines are joined and extra spaces removed"""
    lines = Environment.concatenated([
        'abc  \\\n',
        '   123  \\\n',
        '?\n',
        'MMM\n',
    ])
    assert list(lines) == ['abc 123 ?', 'MMM']


def test_parse_hashes_with_comment():
    """Check that sample is parsed"""
    dep = Dependency(
        'lib==ver  --hash=123 --hash=abc    # comment'
    )
    assert dep.hashes == '--hash=123 --hash=abc'


def test_parse_hashes_without_comment():
    """Check that sample is parsed"""
    dep = Dependency(
        'lib==ver  --hash=123 --hash=abc'
    )
    assert dep.valid
    assert dep.hashes == '--hash=123 --hash=abc'


def test_serialize_hashes():
    """Check serialization in pip-tools style"""
    dep = Dependency(
        'lib==ver  --hash=123 --hash=abc    # comment'
    )
    text = dep.serialize()
    assert text == (
        "lib==ver \\\n"
        "    --hash=123 \\\n"
        "    --hash=abc \\\n"
        "    # comment"
    )


def test_relation_cluster():
    """Check cluster propagets both ways"""
    for entry in ['base', 'test', 'local', 'doc']:
        cluster = relation_cluster([
            {'name': 'base', 'refs': []},
            {'name': 'test', 'refs': ['base']},
            {'name': 'local', 'refs': ['test']},
            {'name': 'doc', 'refs': ['base']},
            {'name': 'side', 'refs': []},
        ], entry)
        assert cluster == set(['base', 'doc', 'local', 'test'])


def test_parse_vcs_dependencies():
    """
    Check VCS support
    https://pip.pypa.io/en/stable/reference/pip_install/#vcs-support
    """
    cases = (
        "git://git.myproject.org/MyProject#egg=MyProject",
        "-e git://git.myproject.org/MyProject#egg=MyProject",
        "git+http://git.myproject.org/MyProject#egg=MyProject",
        "-e git+http://git.myproject.org/MyProject#egg=MyProject",
        "git+https://git.myproject.org/MyProject#egg=MyProject",
        "-e git+https://git.myproject.org/MyProject#egg=MyProject",
        "git+ssh://git.myproject.org/MyProject#egg=MyProject",
        "-e git+ssh://git.myproject.org/MyProject#egg=MyProject",
        "git+git://git.myproject.org/MyProject#egg=MyProject",
        "-e git+git://git.myproject.org/MyProject#egg=MyProject",
        "git+file://git.myproject.org/MyProject#egg=MyProject",
        "-e git+file://git.myproject.org/MyProject#egg=MyProject",
        "-e git+git@git.myproject.org:MyProject#egg=MyProject",
        # Passing branch names, a commit hash or a tag name is possible like so:
        "git://git.myproject.org/MyProject.git@master#egg=MyProject",
        "-e git://git.myproject.org/MyProject.git@master#egg=MyProject",
        "git://git.myproject.org/MyProject.git@v1.0#egg=MyProject",
        "-e git://git.myproject.org/MyProject.git@v1.0#egg=MyProject",
        "git://git.myproject.org/MyProject.git@"
        "da39a3ee5e6b4b0d3255bfef95601890afd80709#egg=MyProject",
        "-e git://git.myproject.org/MyProject.git@"
        "da39a3ee5e6b4b0d3255bfef95601890afd80709#egg=MyProject",
        # Mercurial
        "hg+http://hg.myproject.org/MyProject#egg=MyProject",
        "-e hg+http://hg.myproject.org/MyProject#egg=MyProject",
        "hg+https://hg.myproject.org/MyProject#egg=MyProject",
        "-e hg+https://hg.myproject.org/MyProject#egg=MyProject",
        "hg+ssh://hg.myproject.org/MyProject#egg=MyProject",
        "-e hg+ssh://hg.myproject.org/MyProject#egg=MyProject",
        # You can also specify a revision number, a revision hash,
        # a tag name or a local branch name like so:
        "hg+http://hg.myproject.org/MyProject@da39a3ee5e6b#egg=MyProject",
        "-e hg+http://hg.myproject.org/MyProject@da39a3ee5e6b#egg=MyProject",
        "hg+http://hg.myproject.org/MyProject@2019#egg=MyProject",
        "-e hg+http://hg.myproject.org/MyProject@2019#egg=MyProject",
        "hg+http://hg.myproject.org/MyProject@v1.0#egg=MyProject",
        "-e hg+http://hg.myproject.org/MyProject@v1.0#egg=MyProject",
        "hg+http://hg.myproject.org/MyProject@special_feature#egg=MyProject",
        "-e hg+http://hg.myproject.org/MyProject@special_feature#egg=MyProject",
        # Subversion
        "svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject",
        "-e svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject",
        "svn+http://svn.myproject.org/svn/MyProject/trunk@2019#egg=MyProject",
        "-e svn+http://svn.myproject.org/svn/MyProject/trunk@2019#egg=MyProject",
        # Bazaar
        "bzr+http://bzr.myproject.org/MyProject/trunk#egg=MyProject",
        "-e bzr+http://bzr.myproject.org/MyProject/trunk#egg=MyProject",
        "bzr+sftp://user@myproject.org/MyProject/trunk#egg=MyProject",
        "-e bzr+sftp://user@myproject.org/MyProject/trunk#egg=MyProject",
        "bzr+ssh://user@myproject.org/MyProject/trunk#egg=MyProject",
        "-e bzr+ssh://user@myproject.org/MyProject/trunk#egg=MyProject",
        "bzr+ftp://user@myproject.org/MyProject/trunk#egg=MyProject",
        "-e bzr+ftp://user@myproject.org/MyProject/trunk#egg=MyProject",
        "bzr+lp:MyProject#egg=MyProject",
        "-e bzr+lp:MyProject#egg=MyProject",
        # Tags or revisions can be installed like so:
        "bzr+https://bzr.myproject.org/MyProject/trunk@2019#egg=MyProject",
        "-e bzr+https://bzr.myproject.org/MyProject/trunk@2019#egg=MyProject",
        "bzr+http://bzr.myproject.org/MyProject/trunk@v1.0#egg=MyProject",
        "-e bzr+http://bzr.myproject.org/MyProject/trunk@v1.0#egg=MyProject",
        # Zulip
        "-e git+https://github.com/zulip/talon.git@"
        "7d8bdc4dbcfcc5a73298747293b99fe53da55315#egg=talon==1.2.10.zulip1",
        "-e git+https://github.com/zulip/ultrajson@70ac02bec#egg=ujson==1.35+git",
        "-e git+https://github.com/zulip/virtualenv-clone.git@"
        "44e831da39ffb6b9bb5c7d103d98babccdca0456#egg=virtualenv-clone==0.2.6.zulip1",
        '-e "git+https://github.com/zulip/python-zulip-api.git@'
        '0.4.1#egg=zulip==0.4.1_git&subdirectory=zulip"',
        '-e "git+https://github.com/zulip/python-zulip-api.git@'
        '0.4.1#egg=zulip_bots==0.4.1+git&subdirectory=zulip_bots"',
        # AWX:
        "-e git+https://github.com/ansible/ansiconv.git@tower_1.0.0#egg=ansiconv",
        "-e git+https://github.com/ansible/django-qsstats-magic.git@"
        "tower_0.7.2#egg=django-qsstats-magic",
        "-e git+https://github.com/ansible/dm.xmlsec.binding.git@master#egg=dm.xmlsec.binding",
        "-e git+https://github.com/ansible/django-jsonbfield@"
        "fix-sqlite_serialization#egg=jsonbfield",
        "-e git+https://github.com/ansible/docutils.git@master#egg=docutils",

    )
    for line in cases:
        dependency = Dependency(line)
        assert dependency.valid, line
        serialized = dependency.serialize()
        if line.startswith('-e') and 'git+git@' not in line:
            expect = line.split(' ', 1)[1]
        else:
            expect = line
        assert serialized == expect


def test_merged_packages_raise_for_conflict():
    """Check that package x can't be locked to versions 1 and 2"""
    with pytest.raises(RuntimeError):
        merged_packages(
            {
                'a': {'x': 1},
                'b': {'x': 2},
            },
            ['a', 'b']
        )


def test_fix_pin_detects_version_conflict():
    """Check that package x can't be locked to versions 1 and 2"""
    dedup = PackageDeduplicator()
    dedup.on_discover([{'name': 'a', 'refs': ['b']}, {'name': 'b', 'refs': []}])
    dedup.register_packages_for_env('b', {'x': '1'})
    env = Environment('a', deduplicator=dedup)
    ignored_pin = env.fix_pin('x==1')
    assert ignored_pin is None
    with pytest.raises(RuntimeError):
        env.fix_pin('x==2')
