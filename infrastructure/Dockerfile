FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    build-essential openmpi-bin libopenmpi-dev \
    openssh-server openssh-client python3 htop \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /var/run/sshd /root/.ssh && \
    ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa && \
    cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && \
    chmod 600 /root/.ssh/authorized_keys
RUN echo "Host *\n\tStrictHostKeyChecking no\n\tUserKnownHostsFile=/dev/null" > /root/.ssh/config
WORKDIR /workspace
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
