# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup, NavigableString
from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import pkg.platform.types as platform_types
import base64

@register(name="ImageSearchPlugin", description="使用识图网站搜索图片来源",
          version="1.1", author="BiFangKNT")
class ImageSearchPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)

    # 异步初始化
    async def initialize(self):
        pass

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
                    # 移除 "data:image/png;base64," 前缀
                    if base64_image.startswith("data:image/png;base64,"):
                        base64_image = base64_image[len("data:image/png;base64,"):]

                    search_result = await self.search_image(base64_image)
                    if search_result:
                        # 使用 add_return 方法添加回复
                        ctx.add_return('reply', [platform_types.Plain(search_result)])
                        # 阻止该事件默认行为
                        ctx.prevent_default()
                        # 阻止后续插件执行
                        ctx.prevent_postorder()
                break

    async def search_image(self, base64_image):
        try:
            url = "https://saucenao.com/search.php"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }

            # 解码 base64 数据
            try:
                image_data = base64.b64decode(base64_image.encode('utf-8'))
            except Exception as e:
                self.ap.logger.error(f"Base64 解码失败: {e}")
                return "Base64 解码失败，请稍后再试。"

            # 使用 files 参数上传图片
            files = {'file': ('image.png', image_data, 'image/png')}  # 需要提供文件名和 MIME 类型
            data = {'frame': '1', 'hide': '0', 'database': '999'}  # 其他参数

            response = requests.post(url, files=files, data=data, headers=headers)

            if response.status_code == 200:
                return self.parse_result(response.text)
            else:
                return f"请求失败,状态码: {response.status_code}"
        except Exception as e:
            self.ap.logger.error(f"图片搜索失败: {str(e)}")
            return "图片搜索失败,请稍后再试。"

    def parse_result(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        result_div = soup.select_one('.resulttablecontent')

        if result_div:
            result = []

            # 处理 resulttitle
            title_div = result_div.select_one('.resulttitle')
            if title_div:
                strong = title_div.find('strong')
                if strong:
                    key = strong.text.strip(': ')
                    next_sibling = strong.next_sibling
                    if next_sibling and isinstance(next_sibling, NavigableString):
                        if key == 'Creator':
                            key = '创作者'
                        value = next_sibling.strip()
                        result.append(f"{key}：{value}\n")
                    else:
                        result.append(f"图片标题：{strong.text.strip()}\n")
                else:
                    result.append(f"图片标题：{title_div.text.strip()}\n")

            # 处理所有的 resultcontentcolumn
            content_columns = result_div.select('.resultcontentcolumn')
            for column in content_columns:
                strongs = column.find_all('strong')
                if strongs:
                    for strong in strongs:
                        key = strong.text.strip(': ')
                        if key == 'Source':
                            key = '来源'
                        elif key == 'Material':
                            key = '原作'
                        elif key == 'Characters':
                            key = '角色'
                        elif key == 'Author':
                            key = '作者'
                        elif key == 'Member':
                            key = '站点成员'
                        next_element = strong.next_sibling
                        value = ''
                        link_href = ''
                        while next_element:
                            if isinstance(next_element, NavigableString) and next_element.strip():
                                value = next_element.strip()
                                break
                            elif next_element.name == 'a' and next_element.has_attr('href'):
                                value = next_element.text.strip()
                                link_href = next_element['href']
                                break
                            next_element = next_element.next_sibling

                        if link_href:
                            result.append(f"{key}：{value}\n链接：{link_href}\n")
                        else:
                            result.append(f"{key}：{value}\n")
                else:
                    value = column.text.strip()
                    link = column.find('a')
                    if link:
                        href = link.get('href', '')
                        result.append(f"{value}\n链接：{href}\n")
                    else:
                        result.append(f"{value}\n")

            return "\n".join(result)
        else:
            return "未找到匹配的图片信息。"

    def __del__(self):
        pass
