FROM python:3.9.5 as base
WORKDIR /usr/src/app/
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.cloud.tencent.com/pypi/simple
ENV PYTHONPATH="/usr/src/app/:${PYTHONPATH}"
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1 TZ=Asia/Shanghai
ENV TZ Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
#RUN sed -i '278c description=description,use_local_timezone=kwargs.pop('use_local_timezone', True),' /usr/local/lib/python3.9/site-packages/flask_rq2/functions.py

FROM python:3.9.5
ENV TZ Asia/Shanghai
RUN apt update && apt install tzdata && cp /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone
WORKDIR /usr/src/app/
COPY --from=base /usr/local /usr/local
COPY . /usr/src/app/
VOLUME [ "/download", "/download_bt" ]
CMD python3 crawler.py