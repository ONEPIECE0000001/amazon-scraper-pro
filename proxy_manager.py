import random
import requests
import time
from datetime import datetime, timedelta
from itertools import cycle


class ProxyManager:
    """
    代理池管理器
    """
    def __init__(self, proxy_list=None):
        """
        初始化代理管理器
        
        :param proxy_list: 代理列表，如果为None则使用默认列表
        """
        if proxy_list is None:
            # 示例代理列表 - 在实际使用中应使用真实的代理服务
            self.proxy_list = [
                # {
                #     'http': 'http://username:password@proxy-server:port',
                #     'https': 'https://username:password@proxy-server:port'
                # },
            ]
        else:
            self.proxy_list = proxy_list
            
        self.proxy_cycle = cycle(self.proxy_list) if self.proxy_list else None
        self.current_proxy = None
        self.proxy_usage_count = {}
        self.proxy_last_used = {}
        self.proxy_status = {i: True for i in range(len(self.proxy_list))} if self.proxy_list else {}
        
    def get_random_proxy(self):
        """
        获取随机代理
        """
        if not self.proxy_list:
            return None
            
        # 过滤出可用的代理
        available_proxies = [p for i, p in enumerate(self.proxy_list) if self.proxy_status.get(i, True)]
        
        if not available_proxies:
            return None
            
        self.current_proxy = random.choice(available_proxies)
        return self.current_proxy
    
    def get_round_robin_proxy(self):
        """
        轮询获取代理
        """
        if not self.proxy_list:
            return None
            
        if self.proxy_cycle:
            self.current_proxy = next(self.proxy_cycle)
            return self.current_proxy
        
        return None
    
    def test_proxy(self, proxy, timeout=5):
        """
        测试代理是否可用
        
        :param proxy: 代理配置
        :param timeout: 超时时间
        :return: 代理是否可用
        """
        try:
            # 测试代理连接
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxy,
                timeout=timeout
            )
            return response.status_code == 200
        except:
            return False
    
    def mark_proxy_status(self, proxy, is_working):
        """
        标记代理状态
        
        :param proxy: 代理配置
        :param is_working: 代理是否工作正常
        """
        try:
            proxy_index = self.proxy_list.index(proxy)
            self.proxy_status[proxy_index] = is_working
            
            if not is_working:
                # 如果代理不可用，延迟一段时间再试
                self.proxy_last_used[proxy_index] = datetime.now() + timedelta(minutes=10)
        except ValueError:
            pass  # 代理不在列表中
    
    def get_working_proxy(self, max_retries=5):
        """
        获取可用的代理，最多重试max_retries次
        
        :param max_retries: 最大重试次数
        :return: 可用的代理或None
        """
        for _ in range(max_retries):
            proxy = self.get_random_proxy()
            if proxy and self.test_proxy(proxy):
                return proxy
        
        return None


class AmazonProxyManager(ProxyManager):
    """
    专门用于亚马逊爬取的代理管理器
    """
    def __init__(self, proxy_list=None):
        super().__init__(proxy_list)
        self.amazon_test_url = "https://www.amazon.com"
    
    def test_proxy_for_amazon(self, proxy, timeout=10):
        """
        测试代理是否可以访问亚马逊
        
        :param proxy: 代理配置
        :param timeout: 超时时间
        :return: 代理是否可以访问亚马逊
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(
                self.amazon_test_url,
                proxies=proxy,
                headers=headers,
                timeout=timeout
            )
            
            # 检查是否成功访问（状态码200且页面包含预期内容）
            return response.status_code == 200 and 'amazon' in response.text.lower()
        except Exception as e:
            print(f"代理测试失败: {str(e)}")
            return False
    
    def get_working_amazon_proxy(self, max_retries=5):
        """
        获取可以访问亚马逊的代理
        
        :param max_retries: 最大重试次数
        :return: 可用的代理或None
        """
        for _ in range(max_retries):
            proxy = self.get_random_proxy()
            if proxy and self.test_proxy_for_amazon(proxy):
                return proxy
        
        return None


# 示例代理配置（实际使用时请替换为真实代理）
EXAMPLE_PROXY_LIST = [
    # {
    #     'http': 'http://proxy_user:proxy_pass@proxy_host:proxy_port',
    #     'https': 'https://proxy_user:proxy_pass@proxy_host:proxy_port'
    # },
    # {
    #     'http': 'http://proxy_user2:proxy_pass2@proxy_host2:proxy_port2',
    #     'https': 'https://proxy_user2:proxy_pass2@proxy_host2:proxy_port2'
    # }
]


def get_proxy_manager(proxy_list=None):
    """
    获取代理管理器实例
    
    :param proxy_list: 代理列表
    :return: 代理管理器实例
    """
    if proxy_list is None:
        proxy_list = EXAMPLE_PROXY_LIST
    
    return AmazonProxyManager(proxy_list)


if __name__ == "__main__":
    # 测试代理管理器
    pm = get_proxy_manager()
    
    print("测试代理管理器功能...")
    proxy = pm.get_random_proxy()
    print(f"获取随机代理: {proxy}")
    
    working_proxy = pm.get_working_proxy()
    print(f"获取可用代理: {working_proxy}")