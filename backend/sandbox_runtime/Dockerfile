FROM mcr.microsoft.com/playwright:v1.58.2-noble
LABEL drprompt.runtime="react-typescript-v1"
WORKDIR /runtime
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && node node_modules/esbuild/install.js
COPY runner.mjs ./
RUN chmod -R a-w /runtime
USER 1000:1000
WORKDIR /work
ENTRYPOINT ["node", "/runtime/runner.mjs"]
