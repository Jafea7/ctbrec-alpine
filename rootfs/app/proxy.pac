function FindProxyForURL(url, host) {
  if (shExpMatch(host, "*stripchat.com")) {
    return "SOCKS 127.0.0.1:1080";
  } else if (shExpMatch(host, "*chaturbate.com")) {
    return "PROXY 127.0.0.1:8080";
  } else {
    return "DIRECT";
  }
}