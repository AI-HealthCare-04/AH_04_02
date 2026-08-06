# 개발용 컨테이너 — node_modules는 이미지에 미리 설치해두고, 소스는
# docker-compose의 바인드 마운트로 들어온다 (node_modules는 익명 볼륨으로 덮어쓰기 방지).
FROM node:20-alpine

WORKDIR /workspace

COPY package*.json ./
# npm ci로 package-lock.json에 고정된 버전 그대로 설치 — npm install은 lockfile
# 안에서도 semver 범위 내 최신 패치를 새로 받을 수 있어, 로컬(npm ci)과 이 이미지가
# 미묘하게 다른 패키지 버전을 쓰게 될 여지가 있었다.
RUN npm ci

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
