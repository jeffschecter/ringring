import shutil
import os

from distutils.core import setup

with open('requirements.txt') as f:
    REQUIREMENTS = [
        line.strip() for line in f.readlines() if line.strip()]


def move_hook(root_dir, handle):
    src = os.path.join(root_dir, "bin", handle)
    dst = os.path.join(root_dir, ".git", "hooks", handle)
    shutil.copyfile(src, dst)
    shutil.copymode(src, dst)


root_dir = os.path.dirname(os.path.abspath(__file__))
#move_hook(root_dir, "pre-commit")
#move_hook(root_dir, "pre-push")


setup(
    name='ringring',
    version='0.1',
    author='Jeff Schecter',
    author_email='jeffrey.schecter@gmail.com',
    license='MIT',
    description='Webapps with remote telephonic workforces.',
    url='https://github.com/jeffschecter/ringring',
    keywords=['ringring'],
    classifiers=[],
    install_requires=REQUIREMENTS
)
