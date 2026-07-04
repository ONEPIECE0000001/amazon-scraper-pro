import scrapy


class AmazonProductItem(scrapy.Item):
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
    scraped_at = scrapy.Field()
