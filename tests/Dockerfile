FROM centos

ENV PYENV_ROOT /usr/local/pyenv/
ENV PATH /usr/local/pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN mkdir /usr/local/pyenv && \
    yum install -y git openssh-server gcc readline-devel bzip2-devel zlib-devel openssl-devel sqlite-devel make libffi-devel && \
    yum clean all && \
    git clone git://github.com/yyuu/pyenv.git /usr/local/pyenv && \
    git clone git://github.com/yyuu/pyenv-virtualenv.git /usr/local/pyenv/plugins/pyenv-virtualenv && \
    ln -vs /usr/local/pyenv/bin/* /usr/local/pyenv/plugins/*/bin/* /usr/local/bin

RUN pyenv install 2.7.15 && \
    pyenv install 3.4.9  && \
    pyenv install 3.5.6  && \
    pyenv install 3.6.7  && \
    pyenv install 3.7.1  && \
    pyenv global 3.7.1 3.6.7 3.5.6 3.4.9 2.7.15 && \
    pip install tox

ADD runtests.sh /runtests.sh
RUN useradd -m pepper
USER pepper
