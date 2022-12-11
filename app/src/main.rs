use std::env;
use warp::Filter;

enum Cloud {
    GCP,
    Azure,
    None,
}

#[cfg(feature = "azure")]
static CLOUD: Cloud = Cloud::Azure;

#[cfg(feature = "gcp")]
static CLOUD: Cloud = Cloud::GCP;

#[cfg(not(any(feature = "gcp", feature = "azure")))]
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
        Cloud::None => match env::var("PORT") {
            Ok(val) => val.parse().expect("bad port"),
            Err(_) => 3000,
        },
    }
}

#[tokio::main]
async fn main() {
    let hello = warp::any().map(|| format!("Hello, Slowness!"));
    warp::serve(hello).run(([0, 0, 0, 0], port())).await;
}
