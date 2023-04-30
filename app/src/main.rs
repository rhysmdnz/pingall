use serde::Deserialize;
use std::{collections::HashMap, env, time::Instant};
use warp::{
    http::{Response, StatusCode},
    reject::{self, Reject},
    Filter, Rejection, Reply,
};

#[derive(Eq, PartialEq)]
enum Cloud {
    GCP,
    Azure,
    AliCloud,
    AWS,
    None,
}

#[cfg(feature = "azure")]
static CLOUD: Cloud = Cloud::Azure;

#[cfg(feature = "alicloud")]
static CLOUD: Cloud = Cloud::AliCloud;

#[cfg(feature = "gcp")]
static CLOUD: Cloud = Cloud::GCP;

#[cfg(feature = "aws")]
static CLOUD: Cloud = Cloud::AWS;

#[cfg(not(any(
    feature = "gcp",
    feature = "azure",
    feature = "aws",
    feature = "alicloud"
)))]
static CLOUD: Cloud = Cloud::GCP;

fn port() -> u16 {
    match CLOUD {
        Cloud::GCP => env::var("PORT")
            .expect("no port")
            .parse()
            .expect("bad port"),
        Cloud::Azure => env::var("FUNCTIONS_CUSTOMHANDLER_PORT")
            .expect("no port")
            .parse()
            .expect("bad port"),
        Cloud::AWS => panic!("there are no ports on AWS"),
        Cloud::AliCloud => 9000,
        Cloud::None => match env::var("PORT") {
            Ok(val) => val.parse().expect("bad port"),
            Err(_) => 3000,
        },
    }
}

#[derive(Deserialize)]
pub struct URLQuery {
    url: String,
}

#[derive(Debug)]

enum Error {
    ReqwestError(reqwest::Error),
}

impl warp::reject::Reject for Error {}

pub async fn fetch_url(query: URLQuery) -> Result<impl Reply, Rejection> {
    let start = Instant::now();
    let response = reqwest::get(query.url)
        .await
        .map_err(|e| reject::custom(Error::ReqwestError(e)))?;
    response.status();
    let duration = start.elapsed();
    Ok(format!("{:}", duration.as_millis()))
}

#[tokio::main]
async fn main() {
    let hello = warp::any().and(warp::query()).and_then(fetch_url);

    #[cfg(feature = "aws")]
    lambda_web::run_hyper_on_lambda(warp::service(hello))
        .await
        .unwrap();

    #[cfg(not(feature = "aws"))]
    warp::serve(hello).run(([0, 0, 0, 0], port())).await;
}
