import base64
import uuid

from django.core.files.base import ContentFile

from djoser.serializers import UserSerializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from drf_extra_fields.fields import Base64ImageField

from recipes.models import (FavoriteRecipe, Ingredient, IngredientAmount,
                            Recipe, ShoppingCart, Subscription, Tag)
from users.models import User


class UserListSerializer(UserSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Subscription.objects.filter(user=user, author=obj).exists()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('__all__')


class IngredientAmountSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id',)
    name = serializers.ReadOnlyField(source='ingredient.name',)
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit',
    )

    class Meta:
        model = IngredientAmount
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    author = UserListSerializer(read_only=True)
    image = Base64ImageField()
    ingredients = serializers.SerializerMethodField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'ingredients', 'text',
                  'is_favorited', 'is_in_shopping_cart', 'author', 'image',
                  'cooking_time', 'name', 'pub_date')

    def get_is_favorited(self, obj):
        return (self.context.get('request').user.is_authenticated
                and FavoriteRecipe.objects.filter(
                    user=self.context.get('request').user,
                    recipe_id=obj.id).exists())

    def get_is_in_shopping_cart(self, obj):
        return (self.context.get('request').user.is_authenticated
                and ShoppingCart.objects.filter(
                    user=self.context.get('request').user,
                    recipe_id=obj.id).exists())

    def get_ingredients(self, obj):
        queryset = IngredientAmount.objects.filter(recipe=obj)
        return IngredientAmountSerializer(queryset, many=True).data


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr),
                               name=f'{uuid.uuid1()}.{ext}')

        return super().to_internal_value(data)


class IngredientEditSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField()

    class Meta:
        model = Ingredient
        fields = ('id', 'amount')


class RecipeEditSerializer(serializers.ModelSerializer):
    author = UserListSerializer(read_only=True)
    image = Base64ImageField()
    ingredients = IngredientEditSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image', 'name',
                  'text', 'cooking_time', 'id', 'author')

    def validate(self, data):
        for field in ['name', 'text']:
            if not data.get(field):
                raise serializers.ValidationError(
                    f'{field} - поле, обязательное для заполнения.'
                )
        ingredients = data.get('ingredients')
        if not ingredients:
            raise serializers.ValidationError(
                'В рецепте должен быть хотя бы один ингредиент.'
            )
        if len(ingredients) != len(set([item['id'] for item in ingredients])):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться.'
            )
        if not data.get('tags'):
            raise serializers.ValidationError('Укажите хотя бы один тег.')
        cooking_time = data.get('cooking_time')
        if cooking_time > 500 or cooking_time < 1:
            raise serializers.ValidationError(
                'Время приготовления блюда от 1 до 500 минут'
            )
        return data

    def create_ingredients(self, ingredients, recipe):
        IngredientAmount.objects.bulk_create([
            IngredientAmount(
                recipe=recipe,
                ingredient=Ingredient.objects.get(id=ingredient['id']),
                amount=ingredient['amount']
            ) for ingredient in ingredients])

    def create(self, validate_data):
        ingredients = validate_data.pop('ingredients')
        tags = validate_data.pop('tags')
        recipe = Recipe.objects.create(**validate_data)
        recipe.tags.set(tags)
        self.create_ingredients(ingredients, recipe)
        return recipe

    def update(self, recipe, validate_data):
        ingredients = validate_data.pop('ingredients')
        tags = validate_data.pop('tags')
        recipe = super().update(recipe, validate_data)
        recipe.tags.clear()
        recipe.ingredients.clear()
        recipe.tags.set(tags)
        self.create_ingredients(recipe=recipe,
                                ingredients=ingredients)
        recipe.save()
        return recipe

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return RecipeSerializer(instance,
                                context=context).data


class ShortRecipeSerializer(serializers.ModelSerializer):
    '''Сериализатор для просмотра рецепта на главной'''

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(UserListSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )
        read_only_fields = ('email', 'username',
                            'first_name', 'last_name')

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def validate(self, data):
        author = self.instance
        user = self.context.get('request').user
        if Subscription.objects.filter(author=author, user=user).exists():
            raise ValidationError(
                detail='Вы уже подписались на данного пользователя',
                code=status.HTTP_400_BAD_REQUEST
            )
        if author == user:
            raise ValidationError(
                detail='Нельзя подписаться на самого себя',
                code=status.HTTP_400_BAD_REQUEST
            )
        return data

    def get_recipes(self, obj):
        request = self.context.get('request')
        context = {'request': request}
        recipe_limit = request.query_params.get('recipes_limit')
        recipes = obj.recipes.all()
        if recipe_limit:
            recipes = recipes[:int(recipe_limit)]
        serializer = ShortRecipeSerializer(
            recipes, context=context, many=True
        )
        return serializer.data
