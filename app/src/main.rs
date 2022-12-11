use std::env;
use warp::Filter;

enum Cloud {
    GCP,
    Azure,
    None,
}

#[inline(always)]
fn cloud() -> Cloud {
    match option_env!("PINGER_CLOUD") {
        Some("gcp") => Cloud::GCP,
        Some("azure") => Cloud::Azure,
        Some(_) => panic!("bad PINGER_CLOUD"),
        None => Cloud::None,
    }
}

fn port() -> u16 {
    match cloud() {
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
    let hello = warp::any().map(|| format!("Hello, Rhys!"));

    warp::serve(hello).run(([127, 0, 0, 1], port())).await;
}
