# Ansari Operational Manual

Master API Key: **<code>gm_b5wiqov3jk5c62on7m3nt277ae</code></strong>


# Prototyping

We recommend connecting with the GoodMem CLI for prototyping the system. From your local command line, you can run:


```
goodmem --server https://ansari.hosted.pairsys.ai:9090\
        --api-key gm_b5wiqov3jk5c62on7m3nt277ae\
        memory retrieve\
            --post-processor-interactive\
            --space-id efd91f05-87cf-4c4c-a04d-0a970f8d30a7\
        "How many names does God have?"
```


This opens an interactive Terminal UI, or TUI, shown below, that makes it easy to adjust various parameters for experimentation. By specifying multiple **<code>--space-id</code>** parameters, a single query can search many different spaces at once.

You can download the latest goodmem CLI for your architecture from the latest release on GitHub ([link](https://github.com/PAIR-Systems-Inc/goodmem/releases/tag/server-latest)). After you install it, you can upgrade it in place later using the **<code>goodmem upgrade</code>** command.


# Quick Setup

The following sections show how the GoodMem instance was set up for Ansari.


## Memory Spaces

Note, these should be created after the *embedder* is set up.


```
goodmem space create --name "Qurtubi" \
  --embedder-id 692c3aa4-e316-4ae4-9260-d81a81ea478a

goodmem space create --name "Ibn Katheer" \
  --embedder-id 692c3aa4-e316-4ae4-9260-d81a81ea478a

goodmem space create --name "Mawsuah" \
  --embedder-id 692c3aa4-e316-4ae4-9260-d81a81ea478a

root@vultr:~# goodmem space list
SPACE ID                             NAME                           CREATED              PUBLIC
-----------------------------------------------------------------------------------------------
d04d8032-3a9b-4b83-b906-e48458715a7a Qurtubi                        2025-09-19 23:38:44  false
2d1f3227-8331-46ee-9dc2-d9265bfc79f5 Mawsuah                        2025-09-19 23:38:38  false
efd91f05-87cf-4c4c-a04d-0a970f8d30a7 Ibn Katheer                    2025-09-19 18:02:20  false
```



## Rerankers, Embedders, and LLMs


```
goodmem embedder create\
   --display-name "text-embedding-3-small"\
   --model-identifier "text-embedding-3-small"\
   --provider-type OPENAI\
   --credentials "sk-proj-..."\
   --dimensionality 1536\
   --endpoint-url "https://api.openai.com/v1"

goodmem llm create\
   --display-name "OpenAI GPT-5"\
   --provider-type OPENAI\
   --endpoint-url "https://api.openai.com/v1"\
   --model-identifier "gpt-5"\
   --credentials "..."

goodmem reranker create\
   --display-name "Voyage AI Rerank 2.5"\
   --provider-type VOYAGE\
   --endpoint-url "https://api.voyageai.com"\
   --api-path "/v1/rerank"\
   --model-identifier "rerank-2.5"\
   --credentials "..."

goodmem reranker create\
   --display-name "Cohere Rerank 3.5"\
   --provider-type VLLM\
   --endpoint-url "https://api.cohere.com"\
   --api-path "/v2/rerank"\
   --model-identifier "rerank-v3.5"\
   --credentials "..."
```



## Adding Data

Once the spaces are created, you can add the data.


```
# Ibn Katheer
goodmem memory create \
  --space-id efd91f05-87cf-4c4c-a04d-0a970f8d30a7 \
  --file ibn_kathir.txt \
  --content-type "text/plain"

# Mawsuah
goodmem memory create \
  --space-id 2d1f3227-8331-46ee-9dc2-d9265bfc79f5 \
  --file mawsua.txt \
  --content-type "text/plain"

# Qurtubi
goodmem memory create \
  --space-id d04d8032-3a9b-4b83-b906-e48458715a7a \
  --file qurtubi.txt \
  --content-type "text/plain"
```



# Operating Environment

The Ansari RAG infrastructure consists of a server that hosts GoodMem, a cloud PostgreSQL instance, and several commercial inference providers that provide embedding, reranking, and generative AI capabilities.


## GoodMem Server Details

The DNS name [ansari.hosted.pairsys.ai](ansari.hosted.pairsys.ai) is pointing to 45.76.252.68 hosted on Vultr. The server is $50 per month and includes automated backups. It is managed by PAIR Systems and passed along at-cost to Ansari.


<table>
  <tr>
   <td><strong>Field</strong>
   </td>
   <td><strong>Value</strong>
   </td>
  </tr>
  <tr>
   <td>Location
   </td>
   <td>Atlanta
   </td>
  </tr>
  <tr>
   <td>IP Address
   </td>
   <td>45.76.252.68
   </td>
  </tr>
  <tr>
   <td>Username
   </td>
   <td>root
   </td>
  </tr>
  <tr>
   <td>Password
   </td>
   <td>•••••••
   </td>
  </tr>
  <tr>
   <td>vCPU/s
   </td>
   <td>1 vCPU
   </td>
  </tr>
  <tr>
   <td>RAM
   </td>
   <td>8192.00 MB
   </td>
  </tr>
  <tr>
   <td>Storage
   </td>
   <td>50 GB NVMe
   </td>
  </tr>
  <tr>
   <td>Bandwidth
   </td>
   <td>0.15 GB
   </td>
  </tr>
  <tr>
   <td>Label
   </td>
   <td>ansari.hosted.pairsys.ai
   </td>
  </tr>
  <tr>
   <td>OS
   </td>
   <td>Ubuntu 24.04 LTS x64
   </td>
  </tr>
  <tr>
   <td>Auto Backups
   </td>
   <td>Enabled
   </td>
  </tr>
</table>



### Upgrade

The server can be upgraded by issuing: \
 \
<code>docker pull [ghcr.io/pair-systems-inc/goodmem/server:latest](ghcr.io/pair-systems-inc/goodmem/server:latest)</code>


```
cd ~/.goodmem
docker compose down
docker compose pull server
docker compose up -d server
docker logs -f goodmem-server
```



## PostgreSQL Server Details

A NeonDB instance is used for data persistence.


<table>
  <tr>
   <td><strong>Field</strong>
   </td>
   <td><strong>Value</strong>
   </td>
  </tr>
  <tr>
   <td>Protocol
   </td>
   <td>postgresql
   </td>
  </tr>
  <tr>
   <td>Username
   </td>
   <td>neondb_owner
   </td>
  </tr>
  <tr>
   <td>Password
   </td>
   <td>npg_xfc3ht1zPDgp
   </td>
  </tr>
  <tr>
   <td>Host
   </td>
   <td>ep-wandering-forest-ad3a3a8x-pooler.c-2.us-east-1.aws.neon.tech
   </td>
  </tr>
  <tr>
   <td>Database
   </td>
   <td>neondb
   </td>
  </tr>
  <tr>
   <td>Port
   </td>
   <td>(default 5432 – not specified in URI)
   </td>
  </tr>
  <tr>
   <td>SSL Mode
   </td>
   <td>require
   </td>
  </tr>
  <tr>
   <td>Channel Binding
   </td>
   <td>require
   </td>
  </tr>
</table>



## Commercial Inference Providers

OpenAI: 	**<code>sk-proj-3IhtJ...zA3MMA</code></strong>

Voyage: 	**<code>pa-a82qzdX...HU5oA</code></strong>

Cohere: 	**<code>FceDd...bJMxg</code></strong>
