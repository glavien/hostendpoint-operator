FROM python:3.13-slim AS builder

WORKDIR /wheelhouse
COPY hostendpoint_operator/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheelhouse -r requirements.txt

FROM python:3.13-slim

ARG USERNAME=operator
ARG USER_UID=1001
ARG USER_GID=$USER_UID

RUN groupadd --system --gid $USER_GID ${USERNAME}_group && \
    useradd --system --uid $USER_UID --gid $USER_GID \
    --home-dir /nonexistent --no-create-home $USERNAME

WORKDIR /app

COPY --from=builder /wheelhouse /wheelhouse
RUN pip install --no-cache-dir --no-index --find-links=/wheelhouse /wheelhouse/*.whl && \
    rm -rf /wheelhouse

COPY --chown=${USERNAME}:${USERNAME} hostendpoint_operator/ ./hostendpoint_operator/

RUN mkdir /tmp/writable_tmp && \
    chown ${USERNAME}:${USERNAME} /tmp/writable_tmp

USER $USERNAME

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONOPTIMIZE=1
ENV PYTHONHASHSEED=random

# This tells Python to write its .pyc cache files to our writable directory,
# instead of trying to write them into the read-only /app directory.
ENV PYTHONPYCACHEPREFIX=/tmp/writable_tmp

CMD ["python", "-m", "hostendpoint_operator"]