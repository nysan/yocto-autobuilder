
# Exmaple Proxy server configuration

GIT_CORE_CONFIG = "Yes"
GIT_PROXY_IGNORE = "internal.somewhere.com"
GIT_PROXY_COMMAND = "${OEROOT}/scripts/poky-git-proxy-socks-command"

HTTP_PROXY = "proxy.somewhere.com:123"
HTTP_PROXY_IGNORE = "internal.somewhere.com"

FTP_PROXY = "proxy.somewhere.com:234"
FTP_PROXY_IGNORE = "internal.somewhere.com"

export GIT_PROXY_HOST = "proxy.somewhere.com"
export GIT_PROXY_PORT = "345"
export ftp_proxy = "proxy.somewhere.com:567"
export http_proxy = proxy.somewhere.com:456"

PREMIRRORS_append () {
    ftp://.*/.*    http://internal-mirror.somewhere.com/sources/
    http://.*/.*   http://internal-mirror.somewhere.com/sources/
    https://.*/.*  http://internal-mirror.somewhere.com/sources/
}

