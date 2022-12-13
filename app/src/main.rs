use std::{collections::HashMap, env};
use warp::Filter;

#[derive(Eq, PartialEq)]
enum Cloud {
    GCP,
    Azure,
    AWS,
    None,
}

#[cfg(feature = "azure")]
static CLOUD: Cloud = Cloud::Azure;

#[cfg(feature = "gcp")]
static CLOUD: Cloud = Cloud::GCP;

#[cfg(feature = "aws")]
static CLOUD: Cloud = Cloud::AWS;

#[cfg(not(any(feature = "gcp", feature = "azure", feature = "aws")))]
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
        Cloud::None => match env::var("PORT") {
            Ok(val) => val.parse().expect("bad port"),
            Err(_) => 3000,
        },
    }
}

#[tokio::main]
async fn main() {
    let hello = warp::any()
        .and(warp::query::<HashMap<String, String>>())
        .map(|p: HashMap<String, String>| match p.get("name") {
            Some(name) => format!("Hello, {}!", name),
            None => format!("Hello, World!"),
        });

    #[cfg(feature = "aws")]
    lambda_web::run_hyper_on_lambda(warp::service(hello))
        .await
        .unwrap();

    #[cfg(not(feature = "aws"))]
    warp::serve(hello).run(([0, 0, 0, 0], port())).await;
}
