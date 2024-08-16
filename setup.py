from setuptools import setup
setup(
    name='usos_tools',
    version='0.1',
    description='A Python package for working with USOSweb and USOS API',
    packages=['usos_tools'],
    install_requires=[
        'beautifulsoup4',
        'jsonpickle',
        'requests',
        'matplotlib'
    ]
)
