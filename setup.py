#!venv/bin/python

import os
import shutil
from setuptools import setup, Command
from distutils.errors import DistutilsSetupError
import carson
import versioneer


class FlitCommand(Command):
    description = 'Generic `flit` command'
    user_options = [
        ('format', 'f', 'Select a format. Options: "wheel", "sdist"'),
        ('force', None, 'Force command despite dirty or errant repository')
    ]

    def initialize_options(self):
        self.format = 'wheel'
        self.force = False

    def finalize_options(self):
        if dirty and not self.force:
            raise DistutilsSetupError(f'Dirty repository!  Use --force to override.')
        if self.format not in ('wheel', 'sdist'):
            raise DistutilsSetupError(f'--format must be either "wheel" or "dist".')

    def run(self):
        raise NotImplementedError()


class FlitBuildCommand(FlitCommand):
    description = 'Build everything needed to install using `flit`'

    def run(self):
        cmd = f'flit build --format {self.format}'
        if self.verbose:
            print(cmd)
        if os.system(cmd):
            raise SystemExit(1)


class FlitPublishCommand(FlitCommand):
    description = 'Upload wheel and sdist using `flit`'
    user_options = FlitCommand.user_options + [
        ('repository', 'r', 'Name of the repository to upload to (must be in ~/.pypirc)')
    ]

    def run(self):
        cmd = f'flit publish --format {self.format}'
        if self.verbose:
            print(cmd)
        if os.system(cmd):
            raise SystemExit(1)


class CleanCommand(Command):
    description = 'Clean build from `flit` and remove __pycache__ directories'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        path = os.path.dirname(os.path.abspath(__file__))
        dist_path = os.path.join(path, 'dist')

        if os.path.isdir(dist_path):
            if self.verbose > 1:
                print(f'shutil.rmtree({dist_path!r})')
            shutil.rmtree(dist_path)

        for root, dirs, _ in os.walk(path):
            for d in list(dirs):
                if d.startswith('.'):
                    dirs.remove(d)
            if '__pycache__' in dirs:
                if self.verbose > 1:
                    print(f"shutil.rmtree(os.path.join({root!r}, '__pycache__'))")
                shutil.rmtree(os.path.join(root, '__pycache__'))


class VersionCommand(Command):
    description = 'Print current version from versioneer'
    user_options = []
    verbose = 0

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        vstr = '!!ERROR!!' if error else ''
        if error and error is not True:
            vstr += f'={error!r}'

        vstr = f'{vstr} Version: {version!r}'.strip()
        if self.verbose:
            vstr += f'\n  full: {versions.get("full-revisionid")}'
            vstr += f'\n  date: {versions.get("date")}'
        print(vstr)


versions = versioneer.get_versions()
version = versions.get('version')
error = versions.get('error', True)
dirty = versions.get('dirty')
cmdclasses = versioneer.get_cmdclass()
cmdclasses.update({
    'build': FlitBuildCommand,
    'publish': FlitPublishCommand,
    'upload': FlitPublishCommand,
    'clean': CleanCommand,
    'version': VersionCommand
})

args = {
    'verbose': 0,
    'cmdclass': cmdclasses,
    'name': carson.__title__,
    'version': carson.__version__,
    'description': carson.__summary__,
    'author': carson.__author__,
    'author_email': carson.__email__,
    'url': carson.__uri__,
}

setup(**args)
