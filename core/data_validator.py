import re
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional


class DataValidator:
    """
    数据验证器 - 验证采集到的亚马逊商品数据质量
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_rules = {
            'product_id': self.validate_product_id,
            'name': self.validate_name,
            'price': self.validate_price,
            'rating': self.validate_rating,
            'review_count': self.validate_review_count,
            'brand': self.validate_brand,
            'category': self.validate_category
        }
    
    def validate_product_id(self, product_id: str) -> bool:
        """验证商品ID格式"""
        if not product_id or not isinstance(product_id, str):
            return False
        # 亚马逊ASIN通常为10位字符，包含字母和数字
        return bool(re.match(r'^[A-Z0-9]{10}$', product_id.strip()))
    
    def validate_name(self, name: str) -> bool:
        """验证商品名称"""
        if not name or not isinstance(name, str):
            return False
        name = name.strip()
        return len(name) >= 3 and len(name) <= 500  # 合理的商品名称长度
    
    def validate_price(self, price: str) -> bool:
        """验证价格格式"""
        if not price or price == "N/A":
            return True  # N/A是可接受的值
        
        if not isinstance(price, str):
            return False
            
        # 提取价格数字部分
        price_match = re.search(r'[\d,]+\.?\d*', price.replace('$', '').replace(',', ''))
        if not price_match:
            return False
            
        try:
            price_val = float(price_match.group())
            return 0 <= price_val <= 100000  # 价格在合理范围内
        except ValueError:
            return False
    
    def validate_rating(self, rating: str) -> bool:
        """验证评分"""
        if not rating or rating == "N/A":
            return True  # N/A是可接受的值
            
        if not isinstance(rating, str):
            return False
            
        # 提取评分数字
        rating_match = re.search(r'[\d.]+', rating)
        if not rating_match:
            return False
            
        try:
            rating_val = float(rating_match.group())
            return 0 <= rating_val <= 5.0  # 评分在0-5之间
        except ValueError:
            return False
    
    def validate_review_count(self, review_count: str) -> bool:
        """验证评论数"""
        if not review_count or review_count == "N/A":
            return True  # N/A是可接受的值
            
        if not isinstance(review_count, str):
            return False
            
        # 提取数字
        review_match = re.search(r'\d+', review_count.replace(',', ''))
        if not review_match:
            return False
            
        try:
            review_val = int(review_match.group())
            return 0 <= review_val <= 10000000  # 评论数在合理范围内
        except ValueError:
            return False
    
    def validate_brand(self, brand: str) -> bool:
        """验证品牌"""
        if not brand or brand == "N/A":
            return True  # N/A是可接受的值
            
        if not isinstance(brand, str):
            return False
            
        brand = brand.strip()
        return 1 <= len(brand) <= 100  # 品牌名称长度合理
    
    def validate_category(self, category: str) -> bool:
        """验证分类"""
        if not category or category == "N/A":
            return True  # N/A是可接受的值
            
        if not isinstance(category, str):
            return False
            
        category = category.strip()
        return 1 <= len(category) <= 200  # 分类名称长度合理
    
    def validate_row(self, row_data: Dict[str, Any]) -> Dict[str, bool]:
        """验证单行数据"""
        results = {}
        
        for field, validator in self.validation_rules.items():
            value = row_data.get(field, None)
            results[field] = validator(value)
        
        return results
    
    def validate_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """验证整个数据框"""
        validation_results = {
            'total_rows': len(df),
            'valid_rows': 0,
            'invalid_rows': [],
            'field_validation': {},
            'data_quality_score': 0.0
        }
        
        # 初始化字段验证计数
        for field in self.validation_rules.keys():
            validation_results['field_validation'][field] = {
                'valid': 0,
                'invalid': 0
            }
        
        # 逐行验证
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_validation = self.validate_row(row_dict)
            
            # 检查整行是否有效（所有必需字段都有效）
            row_is_valid = all(row_validation.values())
            
            if row_is_valid:
                validation_results['valid_rows'] += 1
            else:
                validation_results['invalid_rows'].append({
                    'index': idx,
                    'data': row_dict,
                    'errors': {k: v for k, v in row_validation.items() if not v}
                })
            
            # 更新字段验证计数
            for field, is_valid in row_validation.items():
                if is_valid:
                    validation_results['field_validation'][field]['valid'] += 1
                else:
                    validation_results['field_validation'][field]['invalid'] += 1
        
        # 计算数据质量得分
        if validation_results['total_rows'] > 0:
            validation_results['data_quality_score'] = (
                validation_results['valid_rows'] / validation_results['total_rows']
            ) * 100
        
        return validation_results
    
    def get_validation_report(self, validation_results: Dict[str, Any]) -> str:
        """生成验证报告"""
        report = []
        report.append("=== 数据验证报告 ===")
        report.append(f"总行数: {validation_results['total_rows']}")
        report.append(f"有效行数: {validation_results['valid_rows']}")
        report.append(f"无效行数: {len(validation_results['invalid_rows'])}")
        report.append(f"数据质量得分: {validation_results['data_quality_score']:.2f}%")
        report.append("")
        
        report.append("字段验证详情:")
        for field, counts in validation_results['field_validation'].items():
            total = counts['valid'] + counts['invalid']
            if total > 0:
                valid_pct = (counts['valid'] / total) * 100
                report.append(f"  {field}: {counts['valid']}/{total} ({valid_pct:.1f}%) 有效")
        
        if validation_results['invalid_rows']:
            report.append("")
            report.append("无效数据示例:")
            for i, invalid_row in enumerate(validation_results['invalid_rows'][:5]):  # 只显示前5个
                report.append(f"  行 {invalid_row['index']}: {invalid_row['errors']}")
        
        return "\n".join(report)


class DataQualityMonitor:
    """
    数据质量监控器
    """
    
    def __init__(self, min_quality_score: float = 95.0):
        self.validator = DataValidator()
        self.min_quality_score = min_quality_score
        self.logger = logging.getLogger(__name__)
        
    def monitor_data_quality(self, df: pd.DataFrame) -> bool:
        """监控数据质量"""
        validation_results = self.validator.validate_dataframe(df)
        
        self.logger.info(f"数据质量得分: {validation_results['data_quality_score']:.2f}%")
        
        if validation_results['data_quality_score'] < self.min_quality_score:
            self.logger.warning(f"数据质量低于阈值 {self.min_quality_score}%")
            self.logger.info(self.validator.get_validation_report(validation_results))
            return False
        
        self.logger.info("数据质量符合要求")
        return True
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理数据"""
        original_count = len(df)
        
        # 删除完全重复的行
        df = df.drop_duplicates()
        
        # 标记每行的验证状态
        valid_rows = []
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_validation = self.validator.validate_row(row_dict)
            # 只有关键字段都有效才保留
            if (row_validation.get('product_id', False) and 
                row_validation.get('name', False) and 
                row_validation.get('price', True)):  # 价格不是必需的
                valid_rows.append(row)
        
        cleaned_df = pd.DataFrame(valid_rows)
        
        self.logger.info(f"数据清理完成: {original_count} -> {len(cleaned_df)} 行")
        return cleaned_df


def validate_amazon_data_file(file_path: str) -> Dict[str, Any]:
    """
    验证亚马逊数据文件（支持 CSV / Excel）

    :param file_path: CSV 或 Excel 文件路径
    :return: 验证结果
    """
    logger = logging.getLogger(__name__)
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        validator = DataValidator()
        results = validator.validate_dataframe(df)

        logger.info(validator.get_validation_report(results))

        return results
    except Exception as e:
        logger.error("验证文件时出错: %s", str(e))
        return {}


if __name__ == "__main__":
    from core.logging_config import configure_logging
    logger = configure_logging("data_validator")

    # 创建示例数据进行测试
    sample_data = {
        'product_id': ['B08N5WRWNW', 'B07ZPC9Q4K', 'INVALID_ID'],
        'name': ['Sample Product 1', 'Another Product with Valid Name', 'Short'],
        'price': ['$99.99', 'N/A', '$150.00'],
        'rating': ['4.5 out of 5 stars', 'N/A', '3.2 out of 5 stars'],
        'review_count': ['1,234', 'N/A', '567'],
        'brand': ['Sample Brand', 'Another Brand', 'Third Brand'],
        'category': 'Electronics'
    }

    df = pd.DataFrame(sample_data)

    validator = DataValidator()
    results = validator.validate_dataframe(df)

    logger.info("\n" + validator.get_validation_report(results))

    # 测试数据质量监控
    monitor = DataQualityMonitor()
    is_quality_ok = monitor.monitor_data_quality(df)

    logger.info("数据质量是否符合要求: %s", is_quality_ok)

    # 测试数据清理
    cleaned_df = monitor.clean_data(df)
    logger.info("清理后的数据行数: %d", len(cleaned_df))