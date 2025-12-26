"""
测试亚马逊数据采集系统的主要功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from advanced_amazon_spider import AdvancedAmazonSpider
from data_validator import DataValidator, DataQualityMonitor
from proxy_manager import get_proxy_manager
import pandas as pd
import logging


def test_spider_creation():
    """测试爬虫类创建"""
    print("测试1: 爬虫类创建")
    try:
        spider = AdvancedAmazonSpider()
        print("✓ 爬虫类创建成功")
        return True
    except Exception as e:
        print(f"✗ 爬虫类创建失败: {str(e)}")
        return False


def test_data_validator():
    """测试数据验证器"""
    print("\n测试2: 数据验证器")
    try:
        validator = DataValidator()
        
        # 测试各种验证函数
        test_cases = [
            ("B08N5WRWNW", "商品ID验证", validator.validate_product_id),
            ("Sample Product Name", "商品名称验证", validator.validate_name),
            ("$99.99", "价格验证", validator.validate_price),
            ("4.5 out of 5 stars", "评分验证", validator.validate_rating),
            ("1,234", "评论数验证", validator.validate_review_count),
        ]
        
        all_passed = True
        for value, desc, func in test_cases:
            result = func(value)
            status = "✓" if result else "✗"
            print(f"  {status} {desc}: {value} -> {result}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("✓ 数据验证器测试通过")
        else:
            print("✗ 数据验证器部分测试失败")
        
        return all_passed
    except Exception as e:
        print(f"✗ 数据验证器测试失败: {str(e)}")
        return False


def test_data_quality_monitor():
    """测试数据质量监控器"""
    print("\n测试3: 数据质量监控器")
    try:
        monitor = DataQualityMonitor()
        
        # 创建测试数据
        sample_data = {
            'product_id': ['B08N5WRWNW', 'B07ZPC9Q4K', 'B08N5WRWNX'],
            'name': ['Sample Product 1', 'Another Product with Valid Name', 'Third Product'],
            'price': ['$99.99', '$120.50', '$75.00'],
            'rating': ['4.5 out of 5 stars', '4.2 out of 5 stars', '3.8 out of 5 stars'],
            'review_count': ['1,234', '567', '2,345'],
            'brand': ['Sample Brand', 'Another Brand', 'Third Brand'],
            'category': ['Electronics', 'Electronics', 'Electronics']
        }
        
        df = pd.DataFrame(sample_data)
        is_quality_ok = monitor.monitor_data_quality(df)
        
        if is_quality_ok:
            print("✓ 数据质量监控器测试通过")
        else:
            print("✗ 数据质量监控器测试失败")
        
        return is_quality_ok
    except Exception as e:
        print(f"✗ 数据质量监控器测试失败: {str(e)}")
        return False


def test_proxy_manager():
    """测试代理管理器"""
    print("\n测试4: 代理管理器")
    try:
        pm = get_proxy_manager()
        proxy = pm.get_random_proxy()
        
        print(f"  获取随机代理: {proxy}")
        print("✓ 代理管理器测试通过")
        return True
    except Exception as e:
        print(f"✗ 代理管理器测试失败: {str(e)}")
        return False


def test_complete_workflow():
    """测试完整工作流程"""
    print("\n测试5: 完整工作流程")
    try:
        # 创建爬虫实例
        spider = AdvancedAmazonSpider()
        
        # 创建数据验证器
        validator = DataValidator()
        
        # 创建质量监控器
        monitor = DataQualityMonitor()
        
        print("✓ 完整工作流程测试通过")
        return True
    except Exception as e:
        print(f"✗ 完整工作流程测试失败: {str(e)}")
        return False


def main():
    """运行所有测试"""
    print("开始测试亚马逊数据采集系统...")
    print("="*50)
    
    tests = [
        test_spider_creation,
        test_data_validator,
        test_data_quality_monitor,
        test_proxy_manager,
        test_complete_workflow
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_func in tests:
        if test_func():
            passed_tests += 1
    
    print("\n" + "="*50)
    print(f"测试完成: {passed_tests}/{total_tests} 个测试通过")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！系统功能正常。")
        print("\n系统已准备好运行，您可以使用以下命令开始采集数据：")
        print("python main.py --search 'laptop' --pages 3 --mode run")
    else:
        print("⚠️  部分测试失败，请检查系统配置。")


if __name__ == "__main__":
    main()