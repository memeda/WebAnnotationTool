# 网页标注工具 (Web Annotation Tool)

## Motivation

需要标注一些数据，这边都是使用Excel来标的，但是对于长文本体验不是很好。于是萌生了些一个基于WEB的标注工具。然而不幸的事迟迟没有动手。

现在，又有一个 `抽取业务词` 的任务，初步定义为序列标注任务，因此需要标注出文本中哪些连续区间构成一个业务词。

找了一段时间，发现了两个很好的工具，一个是 [Annotator](https://github.com/openannotation/annotator), 一个是 [brat](https://github.com/nlplab/brat).

第一个主要还是用来写标注的，要做成标注工具比较麻烦（API文档不是太详细）。

第二个是鹏爷推荐，的确强大，不过发现其需要安装在Linux上，需要Apache（当然，似乎也有可能安装在Windows上）。这个部署起来不方便（标注人员不懂这些的...）

因此决定还是自己写一个非常简陋的。

## 需求

- 初始化，从服务端获取该文本含有的高亮词。设置高亮

- 鼠标选中文字，保持高亮

- 选中结束后将有一个确认图标，确认则执行添加业务词逻辑；点击其他区域让图标消失。

- 添加业务词的逻辑。

    1. 向server发送更新，server加入到词典

    2. js更新当前剩余文本下高亮状态（如果后续文本也包含该词，那么就高亮这些）

- 当鼠标移动到高亮区域，点击鼠标，出现删除图标。点击删除，则执行删除逻辑；否则图标消失。

    1. 向server发送更新，server删除该词

    2. js更新后续高亮状态

- server使用sqlite存储待标注数据；每次更改操作执行后保存词表。


## 难度

1. [x] 获取选区

    http://stackoverflow.com/questions/5379120/get-the-highlighted-selected-text?rq=1

2. [x] 高亮文本

3. [ ] 在高亮区域检测点击鼠标

4. [x] 出现图标

5. [ ] 整体事务流

6. [x] 最大的难度——没时间啊！ 不是来做标注工具的，而是做任务啊！ 

# 折衷

1. 放弃使用数据库，而是直接将所有数据加载到内存中

    学会了思想：[利用moudule来实现singleton](http://stackoverflow.com/questions/31875/is-there-a-simple-elegant-way-to-define-singletons)

2. 加入新词后高亮更新采用整体更新，而非增量更新