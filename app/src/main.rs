#[macro_use]
extern crate rocket;
use std::env;

#[get("/")]
fn index() -> &'static str {
    "Hello, world!"
}

#[launch]
fn rocket() -> _ {
    let port: u16 = match env::var("PORT") {
        Ok(val) => val.parse().expect("Port is not a number!"),
        Err(_) => 3000,
    };
    let figment = rocket::Config::figment().merge(("port", port));
    rocket::custom(figment).mount("/", routes![index])
}
