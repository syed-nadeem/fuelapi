from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        help_text="Starting location",
    )

    end = serializers.CharField(
        help_text="Destination location",
    )
