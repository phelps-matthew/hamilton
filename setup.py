import setuptools

setuptools.setup(
    name="hamilton",
    description="Hi",
    version="1.0.0",
    author="Matthew Phelps",
    author_email="matthewphelps@odysseyconsult.com",
    packages=setuptools.find_packages(),
    install_requires=[
        "pandas",
        "dash",
        "dash-bootstrap-components",
        "skyfield",
        "pytest-asyncio",
        "sigmf",
        "aio-pika",
        "aiohttp",
    ]
)

