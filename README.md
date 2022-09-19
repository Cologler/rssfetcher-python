# rssfetcher

Fetch rss items into a sqlite database so you can do what you want later.

Can use as a sync source for https://github.com/Cologler/RSSViewer.

## How do I use

0. add run script task to NAS task scheduler, 15min run once;
0. use other app (like `RSSViewer`) to read database.

## Configuration

Configuration file use yaml format.

``` yaml
database: <path of database>
feeds:
    <feed id>:
        url: <feed url>
        proxy: 127.0.0.1:1201  # proxy is optional
    ... # more
```

Feed id and feed url are separated to prevent some website may change url later.

## Sqlite database

Columns of table `rss`:

- feed_id: string
- rss_id: string
- title: string
- raw: string - the raw xml string of current rss item.

It is easy to use other software to parse rss items.

## Server Mode

Server mode allow rssfetcher run without task scheduler, and a simple api to read the fetched data.

To run in server mode, use `uvicorn rssfetcher:main`;

To read fetched data, use `http://.../items/?start_rowid=...&limit=...`;
