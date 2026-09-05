use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result, anyhow, bail};
use futures_util::StreamExt;
use reqwest::header::{CONTENT_LENGTH, CONTENT_RANGE, RANGE};
use tokio::fs::{self, OpenOptions};
use tokio::io::AsyncWriteExt;

pub mod cli {
    use std::path::PathBuf;

    use clap::Parser;

    /// mini-wget 命令行参数定义。
    #[derive(Debug, Clone, Parser)]
    #[command(name = "mini-wget", version, about = "一个 Rust 实现的 wget 原型")]
    pub struct Cli {
        /// 要下载的 HTTP/HTTPS URL。
        pub url: String,

        /// 保存到指定文件名。
        #[arg(short = 'o', long = "output")]
        pub output_file: Option<PathBuf>,

        /// 启用断点续传。
        #[arg(long)]
        pub resume: bool,

        /// 单次请求超时时间（秒）。
        #[arg(long, default_value_t = 30)]
        pub timeout: u64,

        /// 失败后的重试次数。
        #[arg(long, default_value_t = 3)]
        pub retries: usize,
    }
}

pub mod url_parser {
    use super::*;
    use url::Url;

    /// 解析后的下载 URL，集中处理协议、主机和默认文件名。
    #[derive(Debug, Clone)]
    pub struct ParsedUrl {
        inner: Url,
    }

    impl ParsedUrl {
        pub fn parse(input: &str) -> Result<Self> {
            let inner = Url::parse(input).with_context(|| format!("无法解析 URL: {input}"))?;
            match inner.scheme() {
                "http" | "https" => Ok(Self { inner }),
                scheme => bail!("只支持 HTTP/HTTPS URL，不支持协议: {scheme}"),
            }
        }

        pub fn as_str(&self) -> &str {
            self.inner.as_str()
        }

        pub fn host(&self) -> Result<&str> {
            self.inner.host_str().context("URL 缺少主机名")
        }

        pub fn port_or_default(&self) -> Result<u16> {
            self.inner
                .port_or_known_default()
                .context("无法确定 URL 端口")
        }

        pub fn default_filename(&self) -> PathBuf {
            let name = self
                .inner
                .path_segments()
                .and_then(|mut segments| segments.next_back())
                .filter(|segment| !segment.is_empty())
                .unwrap_or("index.html");
            PathBuf::from(name)
        }
    }
}

pub mod dns_resolver {
    use super::*;

    /// DNS 解析结果，供调试或未来扩展连接策略使用。
    #[derive(Debug, Clone)]
    pub struct ResolvedEndpoint {
        pub host: String,
        pub port: u16,
        pub addresses: Vec<std::net::SocketAddr>,
    }

    /// 使用 tokio 的异步解析能力解析主机。
    pub async fn resolve(host: &str, port: u16) -> Result<ResolvedEndpoint> {
        let addresses = tokio::net::lookup_host((host, port))
            .await
            .with_context(|| format!("DNS 解析失败: {host}:{port}"))?
            .collect();

        Ok(ResolvedEndpoint {
            host: host.to_string(),
            port,
            addresses,
        })
    }
}

pub mod ssl {
    use super::*;

    /// SSL/TLS 配置入口。reqwest 的 rustls 后端负责 HTTPS 握手和证书校验。
    pub fn configure(builder: reqwest::ClientBuilder) -> reqwest::ClientBuilder {
        builder.https_only(false).use_rustls_tls()
    }

    pub fn client_builder(timeout: Duration) -> reqwest::ClientBuilder {
        configure(reqwest::Client::builder())
            .timeout(timeout)
            .connect_timeout(timeout)
            .pool_idle_timeout(Duration::from_secs(90))
    }
}

pub mod http_client {
    use super::*;

    /// HTTP 客户端封装。内部 reqwest::Client 自带连接池，可复用连接。
    #[derive(Clone)]
    pub struct HttpClient {
        client: reqwest::Client,
    }

    impl HttpClient {
        pub fn new(timeout: Duration) -> Result<Self> {
            let client = crate::ssl::client_builder(timeout)
                .build()
                .context("创建 HTTP 客户端失败")?;
            Ok(Self { client })
        }

        pub async fn get(&self, url: &str, range_start: Option<u64>) -> Result<reqwest::Response> {
            let mut request = self.client.get(url);
            if let Some(start) = range_start {
                request = request.header(RANGE, format!("bytes={start}-"));
            }

            request
                .send()
                .await
                .with_context(|| format!("GET 请求失败: {url}"))
        }
    }
}

pub mod progress {
    use super::*;
    use indicatif::{ProgressBar, ProgressStyle};

    /// 下载进度条，显示百分比、速度、已下载字节和 ETA。
    pub struct DownloadProgress {
        bar: ProgressBar,
    }

    impl DownloadProgress {
        pub fn new(total_size: Option<u64>, initial_position: u64) -> Self {
            let bar = match total_size {
                Some(total) => ProgressBar::new(total),
                None => ProgressBar::new_spinner(),
            };

            bar.set_position(initial_position);
            bar.set_style(progress_style());
            Self { bar }
        }

        pub fn inc(&self, bytes: u64) {
            self.bar.inc(bytes);
        }

        pub fn finish(&self, path: &Path) {
            self.bar
                .finish_with_message(format!("已保存到 {}", path.display()));
        }
    }

    fn progress_style() -> ProgressStyle {
        ProgressStyle::with_template(
            "{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] \
             {bytes}/{total_bytes} ({percent}%) {bytes_per_sec} ETA {eta}",
        )
        .unwrap()
        .progress_chars("#>-")
    }
}

pub mod downloader {
    use super::*;

    /// 下载任务配置。
    #[derive(Debug, Clone)]
    pub struct DownloadConfig {
        pub url: crate::url_parser::ParsedUrl,
        pub output_file: PathBuf,
        pub resume: bool,
        pub timeout: Duration,
        pub retries: usize,
    }

    /// 下载器负责断点续传、重试、落盘和进度更新。
    pub struct Downloader {
        client: crate::http_client::HttpClient,
    }

    impl Downloader {
        pub fn new(timeout: Duration) -> Result<Self> {
            Ok(Self {
                client: crate::http_client::HttpClient::new(timeout)?,
            })
        }

        pub async fn download(&self, config: &DownloadConfig) -> Result<()> {
            let mut last_error = None;

            for attempt in 0..=config.retries {
                match self.download_once(config).await {
                    Ok(()) => return Ok(()),
                    Err(err) if attempt < config.retries => {
                        last_error = Some(err);
                        // 简单退避，避免瞬时故障时立刻重打同一服务。
                        tokio::time::sleep(Duration::from_millis(300 * (attempt as u64 + 1))).await;
                    }
                    Err(err) => return Err(err),
                }
            }

            Err(last_error.unwrap_or_else(|| anyhow!("下载失败")))
        }

        async fn download_once(&self, config: &DownloadConfig) -> Result<()> {
            let existing_len = existing_len(&config.output_file, config.resume).await?;
            let response = self
                .client
                .get(
                    config.url.as_str(),
                    (config.resume && existing_len > 0).then_some(existing_len),
                )
                .await?;

            let status = response.status();
            let ranged = config.resume && existing_len > 0;
            if ranged && status == reqwest::StatusCode::RANGE_NOT_SATISFIABLE {
                // 服务器拒绝 Range：要么本地文件已覆盖整个资源（视为完成，GNU wget 语义），
                // 要么本地长度与服务器资源不一致（陈旧文件，报错比静默成功更安全）。
                let total_from_server = response
                    .headers()
                    .get(CONTENT_RANGE)
                    .and_then(|value| value.to_str().ok())
                    .and_then(|value| value.rsplit('/').next())
                    .and_then(|value| value.parse::<u64>().ok());
                match total_from_server {
                    Some(total) if total != existing_len => bail!(
                        "断点续传校验失败: 本地 {} 字节，服务器资源 {} 字节",
                        existing_len,
                        total
                    ),
                    _ => {
                        let progress =
                            crate::progress::DownloadProgress::new(Some(existing_len), existing_len);
                        progress.finish(&config.output_file);
                        return Ok(());
                    }
                }
            }
            if !status.is_success() {
                bail!("服务器返回错误状态: {status}");
            }

            let append = ranged && status == reqwest::StatusCode::PARTIAL_CONTENT;
            if ranged && !append {
                // 服务器忽略 Range 时从头重下，避免把完整响应追加到旧文件后面。
                fs::remove_file(&config.output_file).await.ok();
            }

            let content_len = response
                .headers()
                .get(CONTENT_LENGTH)
                .and_then(|value| value.to_str().ok())
                .and_then(|value| value.parse::<u64>().ok());
            let initial = if append { existing_len } else { 0 };
            let total = content_len.map(|len| len + initial);
            let progress = crate::progress::DownloadProgress::new(total, initial);

            let mut file = OpenOptions::new()
                .create(true)
                .write(true)
                .append(append)
                .truncate(!append)
                .open(&config.output_file)
                .await
                .with_context(|| format!("打开输出文件失败: {}", config.output_file.display()))?;

            let mut stream = response.bytes_stream();
            while let Some(chunk) = stream.next().await {
                let chunk = chunk.context("读取响应体失败")?;
                file.write_all(&chunk).await.context("写入输出文件失败")?;
                progress.inc(chunk.len() as u64);
            }

            file.flush().await.context("刷新输出文件失败")?;
            progress.finish(&config.output_file);
            Ok(())
        }
    }

    async fn existing_len(path: &Path, resume: bool) -> Result<u64> {
        if !resume {
            return Ok(0);
        }

        match fs::metadata(path).await {
            Ok(metadata) => Ok(metadata.len()),
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(0),
            Err(err) => Err(err).with_context(|| format!("读取文件元数据失败: {}", path.display())),
        }
    }
}

pub use cli::Cli;
pub use downloader::{DownloadConfig, Downloader};
pub use url_parser::ParsedUrl;

pub fn output_path(parsed_url: &ParsedUrl, explicit_output: Option<PathBuf>) -> PathBuf {
    explicit_output.unwrap_or_else(|| parsed_url.default_filename())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_http_and_https_urls() {
        let http = ParsedUrl::parse("http://example.com/file.txt").unwrap();
        let https = ParsedUrl::parse("https://example.com:8443/a/b").unwrap();

        assert_eq!(http.host().unwrap(), "example.com");
        assert_eq!(http.port_or_default().unwrap(), 80);
        assert_eq!(https.port_or_default().unwrap(), 8443);
    }

    #[test]
    fn rejects_unsupported_scheme() {
        let err = ParsedUrl::parse("ftp://example.com/file.txt").unwrap_err();
        assert!(err.to_string().contains("只支持 HTTP/HTTPS"));
    }

    #[test]
    fn derives_default_filename_from_url_path() {
        let file_url = ParsedUrl::parse("https://example.com/releases/mini.tar.gz").unwrap();
        let root_url = ParsedUrl::parse("https://example.com/").unwrap();

        assert_eq!(file_url.default_filename(), PathBuf::from("mini.tar.gz"));
        assert_eq!(root_url.default_filename(), PathBuf::from("index.html"));
    }

    #[test]
    fn explicit_output_overrides_default_filename() {
        let parsed = ParsedUrl::parse("https://example.com/archive.bin").unwrap();
        let output = output_path(&parsed, Some(PathBuf::from("custom.bin")));

        assert_eq!(output, PathBuf::from("custom.bin"));
    }

    #[test]
    fn normalizes_uppercase_scheme_and_host() {
        let parsed = ParsedUrl::parse("HTTP://Example.COM/file.txt").unwrap();

        assert!(parsed.as_str().starts_with("http://"));
        assert_eq!(parsed.host().unwrap(), "example.com");
        assert_eq!(parsed.port_or_default().unwrap(), 80);
    }

    #[test]
    fn default_filename_excludes_query_and_fragment() {
        let parsed = ParsedUrl::parse("https://example.com/report.pdf?token=x&lang=zh#top").unwrap();

        assert_eq!(parsed.default_filename(), PathBuf::from("report.pdf"));
    }

    #[test]
    fn bare_host_url_defaults_to_index_html() {
        let parsed = ParsedUrl::parse("http://example.com").unwrap();

        assert_eq!(parsed.default_filename(), PathBuf::from("index.html"));
    }

    #[test]
    fn userinfo_url_exposes_host_port_and_filename() {
        let parsed = ParsedUrl::parse("http://user:pass@example.com:8080/d/data.bin").unwrap();

        assert_eq!(parsed.host().unwrap(), "example.com");
        assert_eq!(parsed.port_or_default().unwrap(), 8080);
        assert_eq!(parsed.default_filename(), PathBuf::from("data.bin"));
    }

    #[test]
    fn ipv6_host_keeps_brackets() {
        // url crate 的 host_str 保留方括号（[::1]）；下载路径把完整 URL 交给 reqwest，无影响。
        // 已知潜在债：dns_resolver::resolve 若收到带方括号的主机名会解析失败（当前无调用方）。
        let parsed = ParsedUrl::parse("http://[::1]:9000/x").unwrap();

        assert_eq!(parsed.host().unwrap(), "[::1]");
        assert_eq!(parsed.port_or_default().unwrap(), 9000);
    }

    #[test]
    fn relative_url_rejected() {
        assert!(ParsedUrl::parse("example.com/file.txt").is_err());
        assert!(ParsedUrl::parse("").is_err());
    }

    #[test]
    fn percent_encoded_path_keeps_encoding_in_filename() {
        // 钉住当前行为：文件名保留百分号编码（GNU wget 会解码，留作后续改进）。
        let parsed = ParsedUrl::parse("https://example.com/my%20file.txt").unwrap();

        assert_eq!(parsed.default_filename(), PathBuf::from("my%20file.txt"));
    }

    #[test]
    fn default_port_matches_scheme() {
        let http = ParsedUrl::parse("http://example.com/f").unwrap();
        let https = ParsedUrl::parse("https://example.com/f").unwrap();

        assert_eq!(http.port_or_default().unwrap(), 80);
        assert_eq!(https.port_or_default().unwrap(), 443);
    }
}
