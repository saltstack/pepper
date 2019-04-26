FROM centos

ENV PYENV_ROOT /usr/local/pyenv/
ENV PATH /usr/local/pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN mkdir /usr/local/pyenv && \
    yum install -y git openssh-server gcc readline-devel bzip2-devel zlib-devel openssl-devel sqlite-devel make libffi-devel && \
    yum clean all && \
    git clone git://github.com/yyuu/pyenv.git /usr/local/pyenv && \
    ln -vs /usr/local/pyenv/bin/* /usr/local/pyenv/plugins/*/bin/* /usr/local/bin

RUN pyenv install 2.7.16 && \
    pyenv install 3.4.10  && \
    pyenv install 3.5.7  && \
    pyenv install 3.6.8  && \
    pyenv install 3.7.3  && \
    pyenv install 3.8-dev  && \
    pyenv global 3.7.3 3.6.8 3.5.7 3.4.10 2.7.16 && \
    pip install tox
