from setuptools import setup, find_packages


setup(
    name='bsm_online',
    version='0.0.3',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
        'buzzsprout-manager'
    ],
)
