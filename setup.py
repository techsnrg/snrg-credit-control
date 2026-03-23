from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="snrg_credit_control",
    version="1.0.0",
    description="Credit Control workflow for Sales Orders — SNRG India",
    author="SNRG India",
    author_email="nikhil@snrgindia.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
