# -*- coding: utf-8 -*-
from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import pkg.platform.types as platform_types
import re
import os  # 导入 os 模块
from PicImageSearch import SauceNAO
import base64


@register(name="ImageSearchPlugin", description="使用识图网站搜索图片来源",
          version="2.0", author="BiFangKNT")
class ImageSearchPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.saucenao = None  # 初始化 SauceNAO 对象

    # 异步初始化
    async def initialize(self):
        api_key = os.environ.get("SAUCENAO_API_KEY")  # 从环境变量中获取 API 密钥
        if api_key:
            self.saucenao = SauceNAO(api_key=api_key)  # 在初始化时创建 SauceNAO 对象
            self.ap.logger.info("SauceNAO API key loaded from environment variable.")
        else:
            self.ap.logger.warning(
                "SauceNAO API key not found in environment variable. Plugin may not function correctly.")
            self.saucenao = SauceNAO()  # 如果没有API key，则初始化一个不带key的实例

    @handler(PersonNormalMessageReceived)
    @handler(GroupNormalMessageReceived)
    async def on_message(self, ctx: EventContext):
        await self.process_message(ctx)

    async def process_message(self, ctx: EventContext):
        # 检查消息中是否包含图片
        message_chain = ctx.event.query.message_chain
        for message in message_chain:
            if isinstance(message, platform_types.Image):
                base64_image = message.base64
                if base64_image:
                    self.ap.logger.info(
                        f"ImageSearchPlugin.py: Base64 字符串开头 30 个字符 (received): {base64_image[:30]}")

                    # 使用正则表达式移除 "data:image/<format>;base64," 前缀
                    base64_image = re.sub(r'^data:image/[^;]+;base64,', '', base64_image)

                    search_result = await self.search_image(base64_image)
                    if search_result:
                        # 使用 add_return 方法添加回复
                        ctx.add_return('reply', [platform_types.Plain(search_result)])
                        # 阻止该事件默认行为
                        ctx.prevent_default()
                        # 阻止后续插件执行
                        ctx.prevent_postorder()
                break

    def get_attribute(self, obj, attr):
        """
        获取对象的属性值，如果属性不存在或为空，则返回 "没有检索到哦~"。
        """
        value = getattr(obj, attr, None)
        if not value:
            return "没有检索到哦~"
        if attr == 'similarity':
            return str(value) + '%'  # 添加百分号
        return value

    async def search_image(self, base64_image):
        try:
            # 解码 base64 数据
            try:
                image_data = base64.b64decode(base64_image.encode('utf-8'))
            except Exception as e:
                self.ap.logger.error(f"Base64 解码失败: {e}")
                return "Base64 解码失败，请稍后再试。"

            # 使用 PicImageSearch 库搜索图片, 使用 file 参数
            results = await self.saucenao.search(file=image_data)

            if results and results.raw:  # 检查 results 和 results.raw 是否为空
                # 提取相关信息并格式化输出
                first_result = results.raw[0]  # 获取第一个结果

                # 获取属性值，如果为空则显示 "没有检索到哦~"
                title = self.get_attribute(first_result, 'title')
                similarity = self.get_attribute(first_result, 'similarity')
                url = self.get_attribute(first_result, 'url')
                author = self.get_attribute(first_result, 'author')
                author_url = self.get_attribute(first_result, 'author_url')
                index_name = self.get_attribute(first_result, 'index_name')
                source = self.get_attribute(first_result, 'source')

                search_result = (
                    f"相似度: {similarity}\n"
                    f"标题: {title}\n"
                    f"作者: {author}\n"
                    f"作者链接: {author_url}\n"
                    f"来源链接: {source}\n"
                    f"图库链接: {url}\n"
                    f"索引名称: {index_name}"
                )

                return search_result
            else:
                return "没有检索到哦~"

        except Exception as e:
            self.ap.logger.error(f"图片搜索失败: {str(e)}")
            return "图片搜索失败,请稍后再试。"

    def __del__(self):
        if self.saucenao:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self.saucenao.close())
