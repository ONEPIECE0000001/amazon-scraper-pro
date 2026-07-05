import scrapy


class AmazonProductItem(scrapy.Item):
    keyword = scrapy.Field()
    asin = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    original_price = scrapy.Field()
    rating = scrapy.Field()
    review_count = scrapy.Field()
    brand = scrapy.Field()
    category = scrapy.Field()
    seller_name = scrapy.Field()
    availability = scrapy.Field()
    is_prime = scrapy.Field()
    url = scrapy.Field()
    image_url = scrapy.Field()
    description = scrapy.Field()
    date_first_available = scrapy.Field()
    # 第一期新增字段
    bsr = scrapy.Field()                    # Best Sellers Rank
    coupon_text = scrapy.Field()            # 优惠券/折扣信息
    answered_questions = scrapy.Field()     # Q&A 数量
    variation_count = scrapy.Field()        # 变体数量
    fulfillment_type = scrapy.Field()       # FBA / FBM
    sold_by = scrapy.Field()                # 卖家信息
    scraped_at = scrapy.Field()
