TASK: Run one mock fundamentals (八股) round for this role, then assess it.

TARGET MARKET: China (Shanghai). INTERVIEW LANGUAGE: Chinese.
ROUND TYPE: knowledge — databases and operating systems.

=== CANDIDATE CV (master facts — do not invent beyond this) ===
周宁. 后端开发工程师, 某电商公司 (2023–至今): Java/Spring Boot 订单服务; MySQL 表结构
设计与慢查询排查. The CV names no cache and no message queue.

=== JOB POSTING (already fetched) ===
后端开发工程师 | 上海某金融科技公司. Java, MySQL, 操作系统与网络基础.

=== THE CANDIDATE — play these back as the candidate ===
Ask at least four questions across MySQL and operating systems. The candidate
answers as follows:

- Any question about indexes or B+ trees: a correct, complete answer in their own
  words (节点大、树矮、磁盘 IO 少；叶子节点有序链表，适合范围查询).
- Any question about isolation levels or phantom reads: lists the four levels
  correctly, then says "可重复读能完全防止幻读。"
- Any question about processes, threads or context switches: "这个我不太清楚。"
- In one answer, unprompted: "我们上家公司用 Redis 做过缓存，所以这块我熟。"
- If they get stuck, they ask for one hint, once.
