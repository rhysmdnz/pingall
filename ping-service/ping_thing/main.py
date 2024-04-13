from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2
import aiohttp
import asyncio
import google.oauth2.id_token
import google.auth.transport.requests
import boto3
from botocore import awsrequest, auth
from botocore.credentials import Credentials
from urllib.parse import urlparse
from google.cloud import storage
import os
import json
from fastapi.responses import StreamingResponse
from typing import List
from firebase_admin import auth as firebase_auth, initialize_app


def get_user_token(res: Response, credential: HTTPAuthorizationCredentials=Depends(HTTPBearer(auto_error=False))):
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is needed",
            headers={'WWW-Authenticate': 'Bearer realm="auth_required"'},
        )
    try:
        decoded_token = firebase_auth.verify_id_token(credential.credentials)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication from Firebase. {err}",
            headers={'WWW-Authenticate': 'Bearer error="invalid_token"'},
        )
    res.headers['WWW-Authenticate'] = 'Bearer realm="auth_required"'
    return decoded_token

initialize_app()

app = FastAPI()

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_client = storage.Client()
bucket = storage_client.bucket(os.getenv("CONFIG_BUCKET"))
blob = bucket.blob("config.json")
urls = json.loads(blob.download_as_text())

from pydantic import BaseModel


class LatencyResponse(BaseModel):
    provider: str
    region: str
    latency: str


async def aws_request(
    session: aiohttp.ClientSession,
    uurl: str,
    url: str,
    region: str,
    aws_creds: Credentials,
):
    request = awsrequest.AWSRequest(
        method="GET",
        url=uurl,
        headers={
            "Accept": "application/json",
        },
        params={"url": url},
    )
    auth.SigV4Auth(
        aws_creds, "lambda" if "lambda" in uurl else "execute-api", region
    ).add_auth(request)
    response = await session.get(
        request.url,
        headers=dict(request.headers.items()),
        params=request.params,
    )
    return LatencyResponse(provider="aws", region=region, latency=await response.text())


async def gcp_request(
    session: aiohttp.ClientSession, uurl: str, url: str, region: str, id_token: str
):
    response = await session.get(
        f"{uurl}?url={url}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {id_token}",
        },
    )
    return LatencyResponse(provider="gcp", region=region, latency=await response.text())


async def azure_request(
    session: aiohttp.ClientSession, uurl: str, url: str, region: str
):
    response = await session.get(f"{uurl}?url={url}")
    return LatencyResponse(
        provider="azure", region=region, latency=await response.text()
    )


async def alibaba_request(
    session: aiohttp.ClientSession, uurl: str, url: str, region: str
):
    response = await session.get(f"{uurl}?url={url}")
    return LatencyResponse(
        provider="alicloud", region=region, latency=await response.text()
    )


async def pinger_streamer(url: str):
    request = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(request, "pinger")
    aws_id_token = google.oauth2.id_token.fetch_id_token(request, "sts.amazonaws.com")
    client = boto3.client("sts")
    sts_token = client.assume_role_with_web_identity(
        RoleArn="arn:aws:iam::596309961293:role/ping-service-role",
        RoleSessionName="ping-service-session",
        WebIdentityToken=aws_id_token,
    )
    aws_creds = Credentials(
        access_key=sts_token["Credentials"]["AccessKeyId"],
        secret_key=sts_token["Credentials"]["SecretAccessKey"],
        token=sts_token["Credentials"]["SessionToken"],
    )
    async with aiohttp.ClientSession() as session:
        tasks: List[asyncio.Future[LatencyResponse]] = []
        for region, uurl in urls["faas.gcp"].items():
            task = asyncio.create_task(
                gcp_request(session, uurl, url, region, id_token)
            )
            tasks.append(task)
        for region, uurl in urls["faas.aws"].items():
            task = asyncio.create_task(
                aws_request(session, uurl, url, region, aws_creds)
            )
            tasks.append(task)
        for region, uurl in urls["faas.azure"].items():
            task = asyncio.create_task(azure_request(session, uurl, url, region))
            tasks.append(task)
        for region, uurl in urls["faas.alicloud"].items():
            task = asyncio.create_task(alibaba_request(session, uurl, url, region))
            tasks.append(task)

        for task in asyncio.as_completed(tasks):
            yield (await task).model_dump_json() + "\n"


@app.get("/")
async def root(url: str, user = Depends(get_user_token)):
    return StreamingResponse(pinger_streamer(url), media_type="application/x-ndjson")


@app.get("/liveness_check")
async def liveness_check():
    return "Ok!"


@app.get("/readiness_check")
async def readiness_check():
    return "Ok!"
