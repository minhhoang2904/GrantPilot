export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = "mkp-api.fptcloud.com";
    url.protocol = "https:";
    url.port = "";

    const headers = new Headers(request.headers);
    headers.set("Host", "mkp-api.fptcloud.com");

    const newRequest = new Request(url.toString(), {
      method: request.method,
      headers: headers,
      body: request.body,
    });

    return fetch(newRequest);
  },
};
