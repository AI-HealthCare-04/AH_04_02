# 개발용 컨테이너 — node_modules는 이미지에 미리 설치해두고, 소스는
# docker-compose의 바인드 마운트로 들어온다 (node_modules는 익명 볼륨으로 덮어쓰기 방지).
FROM node:20-alpine

WORKDIR /workspace

COPY package*.json ./
RUN npm install

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
