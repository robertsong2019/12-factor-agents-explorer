//! 下载器端到端测试：本地 std TCP 服务器 + 真实 reqwest 客户端。

use std::collections::HashMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

use wget_rust::downloader::DownloadConfig;
use wget_rust::{Downloader, ParsedUrl};

struct ServerHandle {
    port: u16,
    requests: Arc<AtomicUsize>,
}

impl ServerHandle {
    fn request_count(&self) -> usize {
        self.requests.load(Ordering::SeqCst)
    }
}

fn reason(status: u16) -> &'static str {
    match status {
        200 => "OK",
        206 => "Partial Content",
        404 => "Not Found",
        416 => "Range Not Satisfiable",
        500 => "Internal Server Error",
        _ => "Unknown",
    }
}

fn read_request(stream: &mut TcpStream) -> Option<(String, HashMap<String, String>)> {
    let mut buf = [0u8; 4096];
    let mut data = Vec::new();
    loop {
        let n = stream.read(&mut buf).ok()?;
        if n == 0 {
            break;
        }
        data.extend_from_slice(&buf[..n]);
        if data.windows(4).any(|w| w == b"\r\n\r\n") {
            break;
        }
    }
    let text = String::from_utf8_lossy(&data).to_string();
    let head = text.split("\r\n\r\n").next().unwrap_or("");
    let mut lines = head.lines();
    let request_line = lines.next().unwrap_or("").to_string();
    let mut headers = HashMap::new();
    for line in lines {
        if let Some((k, v)) = line.split_once(':') {
            headers.insert(k.trim().to_ascii_lowercase(), v.trim().to_string());
        }
    }
    Some((request_line, headers))
}

fn spawn_server(handler: impl Fn(usize, &str, &HashMap<String, String>) -> (u16, Vec<(String, String)>, Vec<u8>) + Send + Sync + 'static) -> ServerHandle {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind 127.0.0.1:0");
    let port = listener.local_addr().unwrap().port();
    let requests = Arc::new(AtomicUsize::new(0));
    let counter = requests.clone();
    let handler: Arc<dyn Fn(usize, &str, &HashMap<String, String>) -> (u16, Vec<(String, String)>, Vec<u8>) + Send + Sync> = Arc::new(handler);
    std::thread::spawn(move || {
        for stream in listener.incoming() {
            let Ok(mut stream) = stream else { break };
            let handler = handler.clone();
            let counter = counter.clone();
            std::thread::spawn(move || {
                let Some((raw, headers)) = read_request(&mut stream) else { return };
                let n = counter.fetch_add(1, Ordering::SeqCst);
                let (status, extra, body) = handler(n, &raw, &headers);
                let mut resp = format!(
                    "HTTP/1.1 {status} {}\r\nConnection: close\r\nContent-Length: {}\r\n",
                    reason(status),
                    body.len()
                );
                for (k, v) in extra {
                    resp.push_str(&format!("{k}: {v}\r\n"));
                }
                resp.push_str("\r\n");
                let _ = stream.write_all(resp.as_bytes());
                let _ = stream.write_all(&body);
                let _ = stream.flush();
            });
        }
    });
    ServerHandle { port, requests }
}

fn temp_file(name: &str) -> PathBuf {
    let mut p = std::env::temp_dir();
    p.push(format!("wget_rust_e2e_{}_{}", std::process::id(), name));
    let _ = std::fs::remove_file(&p);
    p
}

fn write_file(path: &Path, content: &[u8]) {
    std::fs::write(path, content).expect("write test fixture");
}

fn read_file(path: &Path) -> Vec<u8> {
    std::fs::read(path).expect("read output file")
}

fn config_for(url: &str, out: &Path, resume: bool, retries: usize) -> DownloadConfig {
    DownloadConfig {
        url: ParsedUrl::parse(url).unwrap(),
        output_file: out.to_path_buf(),
        resume,
        timeout: Duration::from_secs(5),
        retries,
    }
}

async fn run_download(cfg: &DownloadConfig) -> anyhow::Result<()> {
    let dl = Downloader::new(Duration::from_secs(5))?;
    dl.download(cfg).await
}

const FULL_BODY: &[u8] = b"hello world";

#[tokio::test]
async fn downloads_full_body_without_range() {
    let out = temp_file("full_body");
    let server = spawn_server(move |n, raw, headers| {
        assert_eq!(n, 0);
        assert!(raw.starts_with("GET /data.txt"));
        assert!(!headers.contains_key("range"), "非续传请求不应携带 Range");
        (200, vec![], FULL_BODY.to_vec())
    });

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, false, 0);
    run_download(&cfg).await.expect("download ok");

    assert_eq!(read_file(&out), FULL_BODY);
    assert_eq!(server.request_count(), 1);
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn resume_sends_range_and_appends_partial_content() {
    let out = temp_file("resume_206");
    write_file(&out, b"hel");
    let server = spawn_server(move |_, _, headers| {
        assert_eq!(headers.get("range").map(String::as_str), Some("bytes=3-"));
        (
            206,
            vec![("Content-Range".into(), "bytes 3-10/11".into())],
            b"lo world".to_vec(),
        )
    });

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, true, 0);
    run_download(&cfg).await.expect("resume ok");

    assert_eq!(read_file(&out), FULL_BODY);
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn server_ignoring_range_truncates_and_redownloads() {
    let out = temp_file("ignore_range");
    write_file(&out, b"hel");
    let server = spawn_server(move |_, _, headers| {
        // 服务器不支持 Range：忽略请求头，返回 200 完整内容。
        assert!(headers.contains_key("range"));
        (200, vec![], FULL_BODY.to_vec())
    });

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, true, 0);
    run_download(&cfg).await.expect("redownload ok");

    assert_eq!(
        read_file(&out),
        FULL_BODY,
        "服务器忽略 Range 时必须从头重下，不得把完整响应追加到旧文件后面"
    );
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn non_resume_overwrites_existing_longer_file() {
    let out = temp_file("overwrite");
    write_file(&out, b"OLD CONTENT THAT IS LONGER THAN BODY");
    let server = spawn_server(|_, _, _| (200, vec![], b"hi".to_vec()));

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, false, 0);
    run_download(&cfg).await.expect("overwrite ok");

    assert_eq!(read_file(&out), b"hi");
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn error_status_retries_then_bails() {
    let out = temp_file("retry_exhaust");
    let server = spawn_server(|_, _, _| (404, vec![], b"nope".to_vec()));

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, false, 1);
    let err = run_download(&cfg).await.expect_err("must fail after retries");

    assert!(err.to_string().contains("服务器返回错误状态"), "unexpected: {err}");
    assert_eq!(server.request_count(), 2, "retries=1 ⇒ 初始 + 1 次重试 = 2 次请求");
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn transient_failure_then_success_within_retries() {
    let out = temp_file("retry_recover");
    let server = spawn_server(|n, _, _| {
        if n == 0 {
            (500, vec![], b"boom".to_vec())
        } else {
            (200, vec![], b"ok".to_vec())
        }
    });

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, false, 2);
    run_download(&cfg).await.expect("transient failure must recover");

    assert_eq!(read_file(&out), b"ok");
    assert_eq!(server.request_count(), 2);
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn resume_of_complete_file_treats_416_as_done() {
    // RED（修复前）：文件已完整，服务器对 bytes=11- 返回 416。
    // GNU wget 语义：报告已完成而非报错。
    let out = temp_file("resume_416_complete");
    write_file(&out, FULL_BODY);
    let server = spawn_server(move |_, _, headers| {
        assert_eq!(headers.get("range").map(String::as_str), Some("bytes=11-"));
        (
            416,
            vec![("Content-Range".into(), "bytes */11".into())],
            b"".to_vec(),
        )
    });

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, true, 0);
    run_download(&cfg).await.expect("完整文件的断点续传应视为成功");

    assert_eq!(read_file(&out), FULL_BODY, "416 完成路径不得改动本地文件");
    let _ = std::fs::remove_file(&out);
}

#[tokio::test]
async fn resume_416_with_length_mismatch_is_stale_file_error() {
    // 416 且服务器总长 ≠ 本地长度 ⇒ 本地文件陈旧/不完整，必须报错而不是静默成功。
    let out = temp_file("resume_416_mismatch");
    write_file(&out, b"hel");
    let server = spawn_server(|_, _, _| {
        (
            416,
            vec![("Content-Range".into(), "bytes */11".into())],
            b"".to_vec(),
        )
    });

    let cfg = config_for(&format!("http://127.0.0.1:{}/data.txt", server.port), &out, true, 0);
    let err = run_download(&cfg).await.expect_err("长度不一致的 416 必须报错");

    assert!(err.to_string().contains("断点续传校验失败"), "unexpected: {err}");
    assert_eq!(read_file(&out), b"hel", "报错路径不得改动本地文件");
    let _ = std::fs::remove_file(&out);
}
